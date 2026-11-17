# Cursor Cloud memory publication

The optional Cursor gateway serves explicitly published ClaudeMem notes. Each request
requires a Cursor-signed managed-run identity with the configured owner and a complete
single-repository claim. The cloud reader exposes `search_notes` and `read_note`.

The local publisher reads the upstream ClaudeMem database using SQLite read-only mode.
Publication marks live in a separate SQLite registry. A note must be an explicitly saved
observation in the exact memory project configured for the chosen repository.

```sh
claudemem-publish mark OBSERVATION_ID --repo hypercrawl
claudemem-publish unpublish OBSERVATION_ID --repo hypercrawl
```

The installed LaunchAgent runs `publisher.py sync` every 60 seconds while the Mac is
awake. It includes current text for marked notes and withdraws unmarked or deleted
observations. A changed source project withdraws its old publication. Unmarked notes
never enter the cloud snapshot. Normal ClaudeMem save and sync behavior continues.

The private Cloud Storage object is atomically replaced using a generation precondition.
The cloud gateway reads the current object on each authenticated request. There is no
container rebuild for a note change. Failed source reads or uploads preserve the current
publication and the pending local marks. Failed cloud reads return an unavailable error.

The Mac publisher uses a dedicated publication credential in an owner-only configuration
file. Cursor agents use their short-lived workload identity and cannot use the publication
endpoint. The runtime uses its GCP service account to read and replace the single snapshot
in a private bucket. Cloud Storage public access prevention must be enforced.

Configuration keys for the Mac publisher are `source`, `registry`, `projects` (repository
slug to exact ClaudeMem project), `endpoint` (HTTPS `/publication`), and `token`. The
gateway requires `CURSOR_OWNER_ID`, `CMEM_PUBLICATION_BUCKET`, and
`CMEM_PUBLISH_TOKEN_SHA256`. Keep credentials, snapshots, and configuration outside Git.
The gateway's bundled `published.json` defines the approved repository set. Online updates
must contain exactly that set and may include up to 200 notes per repository.

## Verification

```sh
uv run --with-requirements cursor-memory/requirements.txt python -m unittest discover -s cursor-memory -q
python3 -m unittest discover -s tests -q
```

Test coverage includes new marked notes, unmarked notes, unpublishing, source deletions and
edits, cross-repository reads, invalid identities, stale writes, and storage/network failure.
Live rollout verification must also publish a synthetic note through the background timer,
read it from its own Cursor project, deny a read from another project, then unpublish it and
verify withdrawal without changing the serving container revision.
