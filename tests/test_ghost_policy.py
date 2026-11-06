"""The ghost's policy pairs: each allowed case next to a near-identical one that must be denied
(docs/ghost/design.md, Evals). Needs the ghost's venv (cedarpy): .venv/bin/python -m unittest."""

import unittest

try:
    from ghost import config, policy
except ImportError:  # the plain python3 run of the stdlib tests
    policy = None

if policy:
    W = policy.Who
    ALEX = W("player", "alex", "member", "lakeside")
    RIA = W("player", "ria", "member", "riverford")
    HEAD = W("player", "hana", "head", "lakeside")
    GUEST = W("player", "gus", "guest")
    OWNER = W("player", "batmanenjoyer1", "owner", "lakeside")
    LAKE_GHOST, RIVER_GHOST = W.ghost("lakeside"), W.ghost("riverford")
    LAKE, RIVER = config.zone_at(350, -230), config.zone_at(300, -60)
    MARKET, COMMONS = config.zone_at(348, -190), config.zone_at(0, 0)
    c = policy.build_context

    # (name, (who, action, zone, context), allowed?, rule that must decide or None)
    PAIRS = [
        ("small build at home", (ALEX, "Build", LAKE, c(40)), True, "member-small-build"),
        ("small build next door", (ALEX, "Build", RIVER, c(40)), False, None),
        ("big build with the head's yes", (ALEX, "Build", LAKE, c(6000, True)), True, "member-big-build"),
        ("big build without it", (ALEX, "Build", LAKE, c(6000)), False, None),
        ("next door with their head's yes", (ALEX, "Build", RIVER, c(40, False, True)), True, "cross-house"),
        ("next door with our head's yes", (ALEX, "Build", RIVER, c(40, True)), False, None),
        ("member builds in the commons", (ALEX, "Build", COMMONS, c(100)), True, "member-small-build"),
        ("guest builds in the commons", (GUEST, "Build", COMMONS, c(100)), False, "no-guest-builds"),
        ("owner builds in the market", (OWNER, "Build", MARKET, c(10)), True, "owner-builds"),
        ("member builds in the market", (ALEX, "Build", MARKET, c(10)), False, "protected"),
        ("head approves at home", (HEAD, "ApproveBuild", LAKE, None), True, "head-approves"),
        ("head approves next door", (HEAD, "ApproveBuild", RIVER, None), False, None),
        ("member approves", (ALEX, "ApproveBuild", LAKE, None), False, None),
        ("member asks the ghost to follow", (ALEX, "Move", COMMONS, None), True, "members-move-ghost"),
        ("guest asks the ghost to follow", (GUEST, "Move", COMMONS, None), False, None),
        ("guest talks", (GUEST, "Say", COMMONS, None), True, "anyone-talks"),
        ("ghost builds at home", (LAKE_GHOST, "Build", LAKE, c(40)), True, "ghost-own-zone"),
        ("ghost builds next door", (LAKE_GHOST, "Build", RIVER, c(40)), False, None),
        ("spirit talks", (policy.SPIRIT, "Say", COMMONS, None), True, "anyone-talks"),
        ("spirit builds", (policy.SPIRIT, "Build", COMMONS, c(1)), False, "spirit-never-builds"),
        ("build on clear ground", (ALEX, "Build", LAKE, c(40, False, False, False)), True, "member-small-build"),
        ("build on top of a building", (ALEX, "Build", LAKE, c(40, False, False, True)), False, "no-building-over-builds"),
        ("owner builds on top of a building", (OWNER, "Build", LAKE, c(40, False, False, True)), False,
         "no-building-over-builds"),
        ("undo your own build", (ALEX, "Undo", LAKE, {"own_build": True}), True, "undo-own"),
        ("undo someone else's", (ALEX, "Undo", LAKE, {"own_build": False}), False, None),
    ]


@unittest.skipIf(policy is None, "needs the ghost venv (cedarpy)")
class PolicyPairs(unittest.TestCase):
    def test_schema(self):
        self.assertEqual(policy.validate(), [])

    def test_pairs(self):
        for name, (who, action, zone, ctx), allowed, rule in PAIRS:
            with self.subTest(name):
                d = policy.authorize(who, action, zone, ctx)
                self.assertEqual(d.allowed, allowed, f"{name}: {d.rules} {d.errors}")
                self.assertFalse(d.errors, name)
                if rule:
                    self.assertIn(rule, d.rules, name)

    def test_requester_and_ghost_both(self):
        # Ria's head said yes to Alex building in Riverford, but the Lakeside ghost may not build there
        d = policy.both(ALEX, LAKE_GHOST, "Build", RIVER, c(40, False, True))
        self.assertFalse(d.allowed)
        self.assertTrue(policy.both(ALEX, RIVER_GHOST, "Build", RIVER, c(40, False, True)).allowed)
        # a guest can't borrow the ghost's rights
        self.assertFalse(policy.both(GUEST, LAKE_GHOST, "Build", LAKE, c(10)).allowed)

    def test_zones(self):
        self.assertEqual(config.zone_at(348, -190).id, "lakeside_market")  # protected wins
        self.assertEqual({z.id for z in config.zones_touching((300, -160, 320, -140))}, {"lakeside", "commons"})


if __name__ == "__main__":
    unittest.main()
