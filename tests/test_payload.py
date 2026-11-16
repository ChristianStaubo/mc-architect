"""The /place body (build.payload) and the /region reader (bridge.decode) share one layout."""

import unittest

from architect.bridge import decode
from architect.build import payload


class PayloadTest(unittest.TestCase):
    def test_round_trip_keeps_every_cell_and_leaves_gaps_alone(self):
        cells = {(10, 64, -3): "minecraft:stone", (11, 64, -3): "minecraft:stone",
                 (13, 65, -1): "minecraft:oak_stairs[facing=north]", (10, 66, -2): "minecraft:glass",
                 (12, 64, -1): "minecraft:stone"}
        body = payload(cells, "t")
        self.assertEqual(body["origin"], [10, 64, -3])
        self.assertEqual(body["size"], [4, 3, 3])
        self.assertEqual(body["label"], "t")
        self.assertIsNone(body["palette"][0])
        back = decode({"min": body["origin"], "size": body["size"], "palette": body["palette"], "rle": body["rle"]})
        self.assertEqual(len(back), 4 * 3 * 3)
        for p, b in cells.items():
            self.assertEqual(back[p], b)
        gaps = {p: b for p, b in back.items() if p not in cells}
        self.assertEqual(len(gaps), 4 * 3 * 3 - len(cells))
        self.assertTrue(all(b is None for b in gaps.values()))

    def test_one_cell(self):
        body = payload({(0, 0, 0): "minecraft:dirt"})
        self.assertEqual(body["rle"], [1, 1])
        self.assertEqual(decode({"min": body["origin"], "size": body["size"], "palette": body["palette"],
                                 "rle": body["rle"]}), {(0, 0, 0): "minecraft:dirt"})


if __name__ == "__main__":
    unittest.main()
