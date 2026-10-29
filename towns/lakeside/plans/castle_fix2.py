"""Two lanterns for the shaded nooks on the castle's east terraces (dark after placing e255). Place with:
./mc.py place towns/lakeside/plans/castle_fix2.py --at 284,-277 --y 118 --no-clear --foundation none --keep-trees"""

from architect.build import Build


def build():
    b = Build("castle_fix2")
    b.set(1, 4, 1, "lantern")   # (285, 122, -276), upper terrace
    b.set(2, 0, 9, "lantern")   # (286, 118, -268), lower terrace by the carrots
    return b
