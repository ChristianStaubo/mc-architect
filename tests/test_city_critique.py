"""The city critic's reply parser: scores are numbers or None, notes are strings, whatever the model wrote.
Needs the ghost's venv (temporalio): .venv/bin/python -m unittest."""

import unittest

try:
    from ghost.city.activities import critique
except ImportError:  # the plain python3 run of the stdlib tests
    critique = None

EMPTY = {"score": None, "keep": "", "fix": ""}


@unittest.skipIf(critique is None, "needs the ghost venv (temporalio)")
class Critique(unittest.TestCase):
    def test_clean_reply(self):
        self.assertEqual(critique('Looks fine.\n{"score": 7, "keep": "the roofs", "fix": "the doors"}'),
                         {"score": 7, "keep": "the roofs", "fix": "the doors"})

    def test_score_out_of_ten(self):
        self.assertEqual(critique('{"score": "6/10", "keep": "", "fix": "x"}')["score"], 6)

    def test_decimal_string(self):
        self.assertEqual(critique('{"score": "7.5"}')["score"], 7.5)

    def test_word_score(self):
        self.assertIsNone(critique('{"score": "great"}')["score"])

    def test_bool_score(self):
        self.assertIsNone(critique('{"score": true}')["score"])

    def test_no_json(self):
        self.assertEqual(critique("I could not open the sheet."), EMPTY)

    def test_json_list(self):
        self.assertEqual(critique('[6, "fine"]'), EMPTY)

    def test_notes_become_strings(self):
        r = critique('{"score": 5, "keep": ["walls"], "fix": null}')
        self.assertEqual((r["keep"], r["fix"]), ("['walls']", ""))


if __name__ == "__main__":
    unittest.main()
