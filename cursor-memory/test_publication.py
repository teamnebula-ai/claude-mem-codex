import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from publication import Publications


class PublicationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "claude-mem.db"
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE observations (id INTEGER, project TEXT, title TEXT, narrative TEXT, metadata TEXT)")
            db.executemany("INSERT INTO observations VALUES (?,?,?,?,?)", [
                (101, "Published-crawl", "Approved", "crawl note", '{"source":"explicit-shared-memory"}'),
                (102, "Published-crawl", "Private", "do not publish", '{"source":"explicit-shared-memory"}'),
                (103, "Published-crawl", "Observed", "automatic history", '{}'),
                (201, "Published-scale", "Scale", "scale note", '{"source":"explicit-shared-memory"}'),
            ])
        self.mapping = {"hypercrawl": "Published-crawl", "hyperscale": "Published-scale"}
        self.publications = Publications(self.db, self.root / "marks.db", self.mapping)

    def test_unmarked_notes_are_absent_and_mark_is_repository_bound(self):
        self.assertTrue(all(not notes for notes in self.publications.snapshot().values()))
        self.publications.mark(101, "hypercrawl")
        self.publications.mark(101, "hypercrawl")
        data = self.publications.snapshot()
        self.assertEqual([note["id"] for note in data["github.com/teamnebula-ai/hypercrawl"]], [101])
        self.assertEqual(data["github.com/teamnebula-ai/hyperscale"], [])
        for note_id, repo in [(201, "hypercrawl"), (103, "hypercrawl"), (101, "unknown")]:
            with self.assertRaises(ValueError):
                self.publications.mark(note_id, repo)

    def test_unpublish_and_source_delete_revoke_on_the_next_snapshot(self):
        self.publications.mark(101, "hypercrawl")
        self.publications.mark(201, "hyperscale")
        with self.assertRaises(ValueError):
            self.publications.unmark(101, "hyperscale")
        self.publications.unmark(101, "hypercrawl")
        with sqlite3.connect(self.db) as db:
            db.execute("DELETE FROM observations WHERE id=201")
        self.assertTrue(all(not notes for notes in self.publications.snapshot().values()))

    def test_marking_preserves_the_upstream_database(self):
        before = self.db.read_bytes()
        self.publications.mark(101, "hypercrawl")
        self.publications.snapshot()
        self.assertEqual(self.db.read_bytes(), before)

    def test_source_update_and_project_change(self):
        self.publications.mark(101, "hypercrawl")
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE observations SET narrative='updated' WHERE id=101")
        self.assertEqual(self.publications.snapshot()["github.com/teamnebula-ai/hypercrawl"][0]["narrative"], "updated")
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE observations SET project='Published-scale' WHERE id=101")
        self.assertEqual(self.publications.snapshot()["github.com/teamnebula-ai/hypercrawl"], [])


if __name__ == "__main__":
    unittest.main()
