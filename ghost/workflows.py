"""A build, as a durable Temporal workflow (docs/ghost/flows.md, flow 2). The workflow only decides the
order; every step that does I/O is an activity. After a crash Temporal replays this code from its
history: finished activities return their recorded results and are not run again.

Signals from ghost-core: decide("yes" | "no"), revise(text), approved(kind). Query: status()."""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from . import activities as A

QUICK = {"start_to_close_timeout": timedelta(seconds=60), "retry_policy": RetryPolicy(maximum_attempts=5)}
WAIT_FOR_YES = timedelta(minutes=30)
WAIT_FOR_APPROVAL = timedelta(hours=1)


@workflow.defn
class BuildWorkflow:
    def __init__(self):
        self.decision = None
        self.revisions = []
        self.approvals = set()
        self.state = "new"

    @workflow.signal
    def decide(self, d: str):
        self.decision = d

    @workflow.signal
    def revise(self, change: dict):
        """{words: what they said, note: the router's reading, context: where they are and look now}."""
        self.revisions.append(change)

    @workflow.signal
    def approved(self, kind: str):
        self.approvals.add(kind)

    @workflow.query
    def status(self) -> str:
        return self.state

    async def _end(self, task_id, state, what=None, data=None, clear=True):
        if clear:
            await workflow.execute_activity(A.clear_preview, task_id, **QUICK)
        if what:
            await workflow.execute_activity(A.tell, args=[task_id, what, data or {}], **QUICK)
        await workflow.execute_activity(A.finish, args=[task_id, state], **QUICK)
        self.state = state
        return state

    @workflow.run
    async def run(self, task_id: int) -> str:
        revision: dict | None = None
        while True:  # design, show, wait for yes / no / a change
            self.state = "designing"
            d = await workflow.execute_activity(
                A.design, args=[task_id, revision], start_to_close_timeout=timedelta(minutes=20),
                heartbeat_timeout=timedelta(seconds=30), retry_policy=RetryPolicy(maximum_attempts=3))
            if not d["ok"]:
                return await self._end(task_id, "failed", "failed", d, clear=False)
            if self.revisions:  # they asked for changes while it was being drawn: redo it before showing anything
                revision = self.revisions.pop(0)
                continue
            await workflow.execute_activity(A.tell, args=[task_id, "preview", d], **QUICK)
            self.state, self.decision = "waiting", None
            try:
                await workflow.wait_condition(lambda: self.decision is not None or bool(self.revisions),
                                              timeout=WAIT_FOR_YES)
            except asyncio.TimeoutError:
                return await self._end(task_id, "dropped", "dropped", {"text": "Nobody said yes, so I put the preview away."})
            if self.revisions and self.decision is None:
                revision = self.revisions.pop(0)
                continue
            if self.decision == "no":
                return await self._end(task_id, "dropped", "dropped")
            break

        while True:  # yes: is it allowed, or whose yes is still needed?
            c = await workflow.execute_activity(A.check, task_id, **QUICK)
            if c["allowed"]:
                break
            if not c.get("needs"):
                return await self._end(task_id, "denied", "denied", c)
            if c["needs"] in self.approvals:  # approved, yet still not allowed: never ask again (no loops)
                return await self._end(task_id, "denied", "denied",
                                       {"why": f"even with that approval it isn't allowed ({', '.join(c.get('rules') or [])})"})
            self.state = "approval"
            await workflow.execute_activity(A.tell, args=[task_id, "needs", c], **QUICK)
            need = c["needs"]
            try:
                await workflow.wait_condition(lambda: need in self.approvals or self.decision == "deny",
                                              timeout=WAIT_FOR_APPROVAL)
            except asyncio.TimeoutError:
                return await self._end(task_id, "dropped", "dropped", {"text": "Nobody approved it in time, so I dropped it."})
            if self.decision == "deny":
                return await self._end(task_id, "denied", "denied", {"why": "it wasn't approved"})

        self.state = "building"
        r = await workflow.execute_activity(
            A.place, task_id, start_to_close_timeout=timedelta(minutes=10), heartbeat_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=8))
        return await self._end(task_id, "done", "built", r)  # the real blocks are there now: drop the preview
