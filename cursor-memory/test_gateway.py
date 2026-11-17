from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from time import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from gateway import ISSUER, AUDIENCE, create_app

class Keys:
    def __init__(self, key):
        self.key = key
    def get_signing_key(self, kid):
        if kid != "fixture":
            raise jwt.PyJWKClientError("unknown key")
        return type("FixtureKey", (), {"key": self.key})()

class GatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name) / "published.json"
        path.write_text(json.dumps({
            "github.com/teamnebula-ai/hypercrawl": [{"id": 101, "title": "Isolation canary", "narrative": "Synthetic HyperCrawl."}],
            "github.com/teamnebula-ai/hyperscale": [{"id": 201, "title": "Isolation canary", "narrative": "Synthetic HyperScale."}],
        }))
        cls.notes_path = path
    def setUp(self):
        self.app = create_app("42", self.notes_path, Keys(self.key.public_key()))
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def token(self, repo="hypercrawl", **overrides):
        now = int(time())
        url = "github.com/teamnebula-ai/" + repo
        claims = dict(owner_user_id="42", iss=ISSUER, aud=AUDIENCE, iat=now, nbf=now-5, exp=now+300,
                      jti="fixture", agent_runtime="managed", cloud_agent_id="bc-fixture",
                      repo_urls=[url], repo_url=url, repo_count=1, sub="user:42")
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "fixture"})

    def rpc(self, client, token, method, params):
        headers = {"Accept": "application/json, text/event-stream"}
        if token:
            headers["Authorization"] = "Bearer " + token
        return client.post("/mcp", json={"jsonrpc":"2.0","id":1,"method":method,"params":params}, headers=headers)
    def call(self, client, token, name, **args):
        result = self.rpc(client, token, "tools/call", {"name":name,"arguments":args})
        self.assertEqual(result.status_code, 200)
        return result.json()["result"]

    def test_two_projects_both_directions(self):
        with TestClient(self.app) as client:
            for repo, allowed, denied in [("hypercrawl", 101, 201), ("hyperscale", 201, 101)]:
                token = self.token(repo.upper())
                result = self.call(client, token, "search_notes", query="Isolation canary")
                self.assertFalse(result.get("isError"))
                self.assertIn(str(allowed), json.dumps(result))
                self.assertNotIn(str(denied), json.dumps(result))
                self.assertFalse(self.call(client, token, "read_note", observation_id=allowed).get("isError"))
                self.assertTrue(self.call(client, token, "read_note", observation_id=denied)["isError"])
                other_repo = "hyperscale" if repo == "hypercrawl" else "hypercrawl"
                self.assertTrue(self.call(client, token, "search_notes", query="canary", project=other_repo)["isError"])
                self.assertTrue(self.call(client, token, "save_note", text="no writes")["isError"])

    def test_reject_bad_and_ambiguous_identity(self):
        with TestClient(self.app) as client:
            for token, status in [
                (None, 401), ("malformed", 401), (self.token(aud="another-service"), 401),
                (self.token(exp=int(time())-120), 401), (self.token(team_id="7"), 403), (self.token(owner_user_id=None), 403),
                (self.token(owner_user_id="7", sub="user:7"), 403), (self.token(sub="user:7"), 403),
                (self.token(repo_urls=None), 403), (self.token(repo_url="github.com/teamnebula-ai/hyperscale"), 403),
                (self.token(repo_count=2), 403), (self.token(agent_runtime="self_hosted"), 403),
                (self.token("unmapped"), 403)
            ]:
                self.assertEqual(self.rpc(client, token, "tools/list", {}).status_code, status)

if __name__ == "__main__":
    unittest.main()
