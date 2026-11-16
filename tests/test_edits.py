"""Edits and undo against a small in-memory world standing in for the bridge: no server."""

import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from architect import bridge, edits
from architect.build import payload

STONE, AIR, GRASS = "minecraft:stone", "minecraft:air", "minecraft:grass_block"


class FakeWorld:
    """What edits needs of the bridge: /region, /place (with WorldEdit-like history and keys), /history,
    /undo, /command. `fail` makes the next place raise, after applying the blocks when `apply_then_fail`."""

    def __init__(self):
        self.cells = {(x, y, z): GRASS if y == 0 else AIR for x in range(10) for y in range(4) for z in range(10)}
        self.hist = []          # newest first: {"id", "min", "before"}
        self.keys = {}          # key -> server id
        self.places = 0
        self.fail = None
        self.apply_then_fail = False
        self.next_id = 1

    def call(self, path, body=None, timeout=180):
        assert path == "/region", path
        lo, hi = body["min"], body["max"]
        box = {(x, y, z): self.cells.get((x, y, z), AIR)
               for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1) for z in range(lo[2], hi[2] + 1)}
        p = payload(box)
        return {"min": p["origin"], "size": p["size"], "palette": p["palette"], "rle": p["rle"]}

    def _apply(self, body):
        new = bridge.decode({"min": body["origin"], "size": body["size"], "palette": body["palette"], "rle": body["rle"]})
        before = {p: self.cells.get(p, AIR) for p, b in new.items() if b is not None}
        changed = 0
        for p, b in new.items():
            if b is not None and self.cells.get(p, AIR) != b:
                self.cells[p] = b
                changed += 1
        sid, self.next_id = self.next_id, self.next_id + 1
        self.hist.insert(0, {"id": sid, "min": list(body["origin"]), "before": before})
        return sid, changed

    def place(self, body):
        self.places += 1
        key = body.get("key")
        if key in self.keys:
            return {"id": self.keys[key], "changed": 0, "repeat": True}
        if self.fail:
            err, self.fail = self.fail, None
            if self.apply_then_fail:
                sid, _ = self._apply(body)
                if key:
                    self.keys[key] = sid
            raise err
        sid, changed = self._apply(body)
        if key:
            self.keys[key] = sid
        return {"id": sid, "changed": changed}

    def history(self):
        return [{"id": h["id"], "min": h["min"]} for h in self.hist]

    def undo(self, edit_id=None):
        h = self.hist.pop(0)
        assert edit_id in (None, h["id"])
        self.cells.update(h["before"])
        return {"id": h["id"]}

    def command(self, cmd):
        return {}

    def module(self):
        return types.SimpleNamespace(call=self.call, place=self.place, history=self.history, undo=self.undo,
                                     command=self.command, decode=bridge.decode)


def house(x0=2, z0=2, w=3, block=STONE):
    return {(x, y, z): block for x in range(x0, x0 + w) for y in range(1, 3) for z in range(z0, z0 + w)}


class EditsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.world = FakeWorld()
        self.original = dict(self.world.cells)
        for name, value in (("DIR", self.dir), ("INDEX", self.dir / "index.jsonl"), ("bridge", self.world.module())):
            p = mock.patch.object(edits, name, value)
            p.start()
            self.addCleanup(p.stop)

    def lines(self):
        return [json.loads(line) for line in (self.dir / "index.jsonl").read_text().splitlines() if line.strip()]

    def test_undo_uses_worldedit_when_the_edit_is_the_servers_latest(self):
        e = edits.place(house(), "hut")
        self.assertEqual(self.world.cells[(3, 1, 3)], STONE)
        u = edits.undo(e["id"])
        self.assertEqual(u["undo_via"], "worldedit")
        self.assertEqual(self.world.cells, self.original)
        self.assertEqual(edits.listing(), [])

    def test_undo_puts_the_snapshot_back_after_a_restart(self):
        e = edits.place(house(), "hut")
        self.world.hist.clear()  # the server restarted: WorldEdit forgot
        u = edits.undo(e["id"])
        self.assertEqual(u["undo_via"], "snapshot")
        self.assertEqual(self.world.cells, self.original)

    def test_an_older_edit_under_a_newer_one_is_refused(self):
        a = edits.place(house(), "a")
        b = edits.place(house(x0=3, z0=3), "b")
        with self.assertRaises(SystemExit) as cm:
            edits.undo(a["id"])
        self.assertIn(b["id"], str(cm.exception))
        self.assertIn(f"overlap {a['id']}", str(cm.exception))

    def test_a_finished_unkeyed_place_has_no_state(self):
        e = edits.place(house(), "hut")
        self.assertNotIn("state", e)
        self.assertNotIn("state", edits.get(e["id"]))
        self.assertEqual([x["state"] for x in self.lines() if "state" in x], ["placing"])  # written before placing
        self.assertEqual([x["id"] for x in edits.listing()], [e["id"]])

    def test_an_interrupted_place_is_recorded_and_can_be_undone(self):
        older = edits.place(house(x0=1, z0=1, w=5, block="minecraft:oak_planks"), "older")
        self.world.fail, self.world.apply_then_fail = TimeoutError("bridge timed out"), True
        with self.assertRaises(TimeoutError):
            edits.place(house(), "cut off")
        placing = [x for x in self.lines() if x.get("state") == "placing" and x["label"] == "cut off"]
        self.assertEqual(len(placing), 1)
        lost = placing[0]["id"]
        self.assertEqual([x["id"] for x in edits.listing()], [older["id"]])
        self.assertEqual([x["id"] for x in edits.interrupted()], [lost])
        self.assertEqual(edits.newest()["id"], older["id"])

        nxt = edits.place({(8, 1, 8): STONE}, "next")
        self.assertNotEqual(nxt["id"], lost)
        self.assertTrue((self.dir / f"{lost}.json.gz").exists())
        self.assertTrue((self.dir / f"{nxt['id']}.json.gz").exists())

        with self.assertRaises(SystemExit) as cm:
            edits.undo(older["id"])
        self.assertIn(lost, str(cm.exception))

        self.world.hist.clear()  # whatever the server remembers, the snapshot is what's trusted here
        u = edits.undo(lost)
        self.assertEqual(u["undo_via"], "snapshot")
        self.assertEqual(edits.interrupted(), [])
        for p, b in house().items():
            self.assertEqual(self.world.cells[p], "minecraft:oak_planks")  # what was there before it
        edits.undo(nxt["id"])
        edits.undo(older["id"])
        self.assertEqual(self.world.cells, self.original)

    def test_the_same_key_twice_places_once(self):
        first = edits.place(house(), "hut", key="k1")
        again = edits.place(house(), "hut", key="k1")
        self.assertEqual(self.world.places, 1)
        self.assertTrue(again["repeat"])
        self.assertEqual(again["id"], first["id"])
        self.assertEqual(first["state"], "applied")

    def test_a_pending_keyed_place_is_retried_with_its_id_and_snapshot(self):
        self.world.fail = ConnectionError("dropped")
        with self.assertRaises(ConnectionError):
            edits.place(house(), "hut", key="k2")
        pending = edits.get("e1")
        self.assertEqual((pending["key"], pending["state"]), ("k2", "pending"))
        self.assertIn("e1", [x["id"] for x in edits.listing()])  # keyed records keep their old visibility
        e = edits.place(house(), "hut", key="k2")
        self.assertEqual((e["id"], e["snapshot"], e["state"]), ("e1", pending["snapshot"], "applied"))
        self.assertEqual(sorted(p.name for p in self.dir.glob("*.json.gz")), ["e1.json.gz"])
        self.assertEqual(self.world.cells[(3, 1, 3)], STONE)


if __name__ == "__main__":
    unittest.main()
