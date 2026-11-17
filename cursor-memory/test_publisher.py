import hashlib
from unittest.mock import patch

from publication import canonical
from publisher import synchronize
from test_publication import PublicationTest


class PublisherTest(PublicationTest):
    def test_unchanged_snapshot_does_not_rewrite_and_new_mark_does(self):
        snapshot = self.publications.snapshot()
        old = {"generation": "7", "digest": hashlib.sha256(canonical(snapshot)).hexdigest()}
        with patch("publisher.remote", return_value=old) as remote:
            synchronize({}, self.publications)
            self.assertEqual(remote.call_count, 1)
        self.publications.mark(101, "hypercrawl")
        new_digest = hashlib.sha256(canonical(self.publications.snapshot())).hexdigest()
        with patch("publisher.remote", side_effect=[old, {"generation": "8", "digest": new_digest}]) as remote:
            receipt = synchronize({}, self.publications)
            self.assertEqual(receipt["notes"], 1)
            self.assertEqual(remote.call_args.args[1], "PUT")
            self.assertEqual(remote.call_args.args[2]["generation"], "7")

    def test_network_failure_keeps_marks_for_the_next_timer(self):
        self.publications.mark(101, "hypercrawl")
        with patch("publisher.remote", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                synchronize({}, self.publications)
        self.assertEqual(self.publications.snapshot()["github.com/teamnebula-ai/hypercrawl"][0]["id"], 101)
