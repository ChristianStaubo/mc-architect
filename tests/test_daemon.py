"""The /arc daemon survives bridge failures and a failed job (no server, no model)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from architect import bridge
from architect.assistant import daemon, sessions


class BridgeTimeoutTest(unittest.TestCase):
    def test_read_timeout_is_bridge_error(self):
        with tempfile.TemporaryDirectory() as d:
            token = Path(d) / "token"
            token.write_text("t")
            with mock.patch.object(bridge, "TOKEN_FILE", token), \
                    mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
                with self.assertRaises(bridge.BridgeError) as cm:
                    bridge._call("/inbox", {}, 5)
        self.assertIn("timed out after 5s on /inbox", str(cm.exception))


class FinishTest(unittest.TestCase):
    def setUp(self):
        daemon.jobs.clear()
        daemon.queue.clear()

    tearDown = setUp

    def test_failed_job_frees_the_player_and_starts_the_next(self):
        job = mock.Mock()
        job.wait.side_effect = RuntimeError("agent crashed")
        daemon.jobs["alice"] = job
        nxt = ({"player": "bob", "text": "a hut"}, "sonnet")
        daemon.queue.append(nxt)
        logs = []
        with mock.patch.object(daemon, "say") as say, mock.patch.object(daemon, "start") as start:
            daemon.finish("alice", job, "arc:alice:1", logs.append)
        self.assertNotIn("alice", daemon.jobs)
        start.assert_called_once_with(*nxt, logs.append)
        say.assert_called_once_with("alice", daemon.SORRY, "warn")
        self.assertTrue(any("finishing failed" in line for line in logs))

    def test_failed_start_of_the_next_tells_that_player(self):
        job = mock.Mock()
        job.wait.side_effect = RuntimeError("agent crashed")
        daemon.jobs["alice"] = job
        daemon.queue.append(({"player": "bob", "text": "a hut"}, "sonnet"))
        with mock.patch.object(daemon, "say", side_effect=bridge.BridgeError("down")) as say, \
                mock.patch.object(daemon, "start", side_effect=OSError("disk")):
            daemon.finish("alice", job, "arc:alice:1", lambda line: None)
        self.assertNotIn("alice", daemon.jobs)
        self.assertEqual([c.args[0] for c in say.call_args_list], ["alice", "bob"])


class ServeTest(unittest.TestCase):
    def test_failed_say_and_ack_do_not_stop_the_loop(self):
        event = {"id": 1, "player": "alice", "kind": "status", "text": ""}
        inbox = mock.Mock(side_effect=[[event], KeyboardInterrupt()])
        with mock.patch.object(bridge, "inbox", inbox), \
                mock.patch.object(bridge, "ack", side_effect=bridge.BridgeError("down")) as ack, \
                mock.patch.object(daemon, "handle", side_effect=RuntimeError("bad event")), \
                mock.patch.object(daemon, "say", side_effect=bridge.BridgeError("down")):
            with self.assertRaises(KeyboardInterrupt):
                daemon.serve(log=lambda line: None)
        self.assertEqual(inbox.call_count, 2)
        ack.assert_called_once_with([1])


class SessionsFileTest(unittest.TestCase):
    def test_edit_writes_a_whole_file(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(sessions, "DIR", Path(d)), \
                    mock.patch.object(sessions, "FILE", Path(d) / "sessions.json"):
                with sessions.edit("Bob") as s:
                    s["x"] = 1
                self.assertEqual(sessions.get("bob")["x"], 1)
                self.assertEqual(list(Path(d).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
