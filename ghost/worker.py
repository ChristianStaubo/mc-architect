"""ghost-worker: the Temporal worker that runs build workflows and their activities. Several can run;
a killed one's work is picked up by another (or by itself after a restart)."""

import asyncio
import concurrent.futures
import os
import threading
import time

from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

from . import activities as A
from . import config, db
from .workflows import BuildWorkflow


def _beat(name):
    while True:
        try:
            db.heartbeat(name, pid=os.getpid())
        except Exception:  # noqa: BLE001 (the watchdog notices missing beats)
            pass
        time.sleep(5)


async def main():
    name = f"ghost-worker-{os.getpid()}"
    threading.Thread(target=_beat, args=(name,), daemon=True).start()
    client = await Client.connect(config.TEMPORAL)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        worker = Worker(client, task_queue=config.TASK_QUEUE, workflows=[BuildWorkflow],
                        activities=[A.design, A.tell, A.clear_preview, A.check, A.place, A.finish],
                        activity_executor=pool, max_concurrent_activities=6,
                        # the workflow imports our activities (for their names); they aren't run inside it
                        workflow_runner=SandboxedWorkflowRunner(
                            restrictions=SandboxRestrictions.default.with_passthrough_modules("ghost", "architect",
                                                                                              "psycopg", "cedarpy")))
        print(f"{name}: waiting for work on {config.TASK_QUEUE}", flush=True)
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
