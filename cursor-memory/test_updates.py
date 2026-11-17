from copy import deepcopy
import hashlib
import json

from starlette.testclient import TestClient
from test_gateway import GatewayTest, Keys
from gateway import create_app


class ObjectFixture:
    def __init__(self, data):
        self.data = data
        self.generation = "1"
        self.unavailable = False

    def load(self):
        if self.unavailable:
            raise OSError("unavailable")
        return self.data, self.generation

    def replace(self, data, generation):
        if generation != self.generation:
            raise ValueError("Snapshot changed")
        self.data = data
        self.generation = str(int(self.generation) + 1)
        return self.generation


class AutomaticUpdateTest(GatewayTest):
    def setUp(self):
        self.store = ObjectFixture(json.loads(self.notes_path.read_text()))
        self.secret = "fixture-publication-credential"
        self.app = create_app("42", self.notes_path, Keys(self.key.public_key()),
                              store=self.store, publish_hash=hashlib.sha256(self.secret.encode()).hexdigest())

    def publication(self, client, method="GET", credential=None, body=None):
        return client.request(method, "/publication", headers={"Authorization": "Bearer " + (credential or self.secret)}, json=body)

    def test_new_note_and_unpublish_work_in_same_running_gateway(self):
        with TestClient(self.app) as client:
            crawl = self.token()
            scale = self.token("hyperscale")
            changed = deepcopy(self.store.data)
            changed["github.com/teamnebula-ai/hypercrawl"].append({"id": 102, "title": "New published note", "narrative": "visible automatically"})
            self.assertEqual(self.publication(client, "PUT", body={"generation": "1", "snapshot": changed}).status_code, 200)
            self.assertFalse(self.call(client, crawl, "read_note", observation_id=102).get("isError"))
            self.assertTrue(self.call(client, scale, "read_note", observation_id=102)["isError"])
            changed["github.com/teamnebula-ai/hypercrawl"] = []
            self.assertEqual(self.publication(client, "PUT", body={"generation": "2", "snapshot": changed}).status_code, 200)
            self.assertTrue(self.call(client, crawl, "read_note", observation_id=102)["isError"])

    def test_cursor_cannot_publish_and_snapshot_cannot_expand_repository_scope(self):
        with TestClient(self.app) as client:
            self.assertEqual(self.publication(client, credential=self.token()).status_code, 401)
            changed = deepcopy(self.store.data)
            changed["github.com/other-org/repo"] = []
            self.assertEqual(self.publication(client, "PUT", body={"generation": "1", "snapshot": changed}).status_code, 400)
            self.assertEqual(self.store.generation, "1")

    def test_stale_generation_and_storage_failure_fail_closed(self):
        with TestClient(self.app) as client:
            self.assertEqual(self.publication(client, "PUT", body={"generation": "0", "snapshot": self.store.data}).status_code, 409)
            self.store.unavailable = True
            self.assertEqual(self.rpc(client, self.token(), "tools/list", {}).status_code, 503)
