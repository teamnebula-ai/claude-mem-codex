"""Explicit publication marks kept separately from upstream ClaudeMem state."""
import json
import re
import sqlite3
from pathlib import Path

REPO = re.compile(r"[a-z0-9._-]+")
SECRET = re.compile(r"-----BEGIN .*PRIVATE KEY|\b(?:ghp_|github_pat_|sk-(?:proj-)?)[A-Za-z0-9_-]{16,}|\bBearer [A-Za-z0-9._~+/=-]{20,}", re.I)


class Publications:
    def __init__(self, source: Path, registry: Path, projects: dict):
        if not projects or any(not REPO.fullmatch(repo) or not isinstance(project, str) or not project for repo, project in projects.items()):
            raise ValueError("Expected an explicit repository to memory-project mapping.")
        if len(set(projects.values())) != len(projects):
            raise ValueError("Each repository must have its own memory project.")
        self.source = source.resolve()
        self.registry = registry
        self.projects = projects
        registry.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect_registry() as db:
            db.execute("CREATE TABLE IF NOT EXISTS marks (id INTEGER PRIMARY KEY, repository TEXT NOT NULL)")
        registry.chmod(0o600)

    def connect_registry(self):
        return sqlite3.connect(self.registry, timeout=5)

    def read(self, db, note_id, repository):
        row = db.execute(
            """SELECT id, title, narrative FROM observations
               WHERE id=? AND project=? AND json_valid(metadata)
               AND json_extract(metadata, '$.source')='explicit-shared-memory'""",
            (note_id, self.projects[repository]),
        ).fetchone()
        if row is None:
            return None
        note = dict(zip(("id", "title", "narrative"), row))
        if not isinstance(note["title"], str) or not 1 <= len(note["title"]) <= 180:
            raise ValueError(f"Invalid title on observation {note_id}.")
        if not isinstance(note["narrative"], str) or not 1 <= len(note["narrative"]) <= 16000:
            raise ValueError(f"Invalid text on observation {note_id}.")
        if SECRET.search(note["title"] + " " + note["narrative"]) or "<private>" in note["narrative"].lower():
            raise ValueError(f"Observation {note_id} contains private or credential-like text.")
        return note

    def source_connection(self):
        return sqlite3.connect(self.source.as_uri() + "?mode=ro", uri=True, timeout=5)

    def mark(self, note_id, repository):
        if type(note_id) is not int or note_id < 1 or repository not in self.projects:
            raise ValueError("Specify a positive observation ID and an approved repository.")
        with self.source_connection() as source:
            if self.read(source, note_id, repository) is None:
                raise ValueError("Observation is outside this repository's explicit-note project.")
        with self.connect_registry() as registry:
            registry.execute("BEGIN IMMEDIATE")
            existing = registry.execute("SELECT repository FROM marks WHERE id=?", (note_id,)).fetchone()
            if existing and existing[0] != repository:
                raise ValueError("Observation is already marked for another repository.")
            registry.execute("INSERT OR IGNORE INTO marks VALUES (?,?)", (note_id, repository))

    def unmark(self, note_id, repository):
        if repository not in self.projects or type(note_id) is not int or note_id < 1:
            raise ValueError("Specify an approved repository and observation ID.")
        with self.connect_registry() as registry:
            registry.execute("BEGIN IMMEDIATE")
            current = registry.execute("SELECT repository FROM marks WHERE id=?", (note_id,)).fetchone()
            if current and current[0] != repository:
                raise ValueError("Observation is marked for another repository.")
            registry.execute("DELETE FROM marks WHERE id=? AND repository=?", (note_id, repository))

    def snapshot(self):
        result = {"github.com/teamnebula-ai/" + repo: [] for repo in self.projects}
        with self.connect_registry() as registry:
            marked = registry.execute("SELECT id, repository FROM marks ORDER BY id").fetchall()
        with self.source_connection() as source:
            source.execute("BEGIN")
            for note_id, repository in marked:
                if repository not in self.projects:
                    raise ValueError("Publication registry contains an unknown repository.")
                note = self.read(source, note_id, repository)
                if note is not None:
                    result["github.com/teamnebula-ai/" + repository].append(note)
        return result


def canonical(snapshot):
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
