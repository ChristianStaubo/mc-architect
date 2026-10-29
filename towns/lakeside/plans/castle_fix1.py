"""Fixes after placing the castle (e255): two stray upside-down stairs at y 129 that hung in the air,
and a lantern for the dark nook under the orchard oak on the east terrace. Place with:
./mc.py place towns/lakeside/plans/castle_fix1.py --at 259,-280 --y 118 --no-clear --foundation none --keep-trees"""

from architect.build import Build


def build():
    b = Build("castle_fix1")
    b.set(0, 11, 0, "air")          # (259, 129, -280)
    b.set(7, 11, 0, "air")          # (266, 129, -280)
    b.set(19, 0, 31, "lantern")     # (278, 118, -249), on the grass under the oak
    return b
