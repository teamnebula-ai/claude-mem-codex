"""Read-only MCP gateway for explicitly published Team Nebula ClaudeMem notes."""
import contextvars
import hashlib
import hmac
import json
import os
import re
from pathlib import Path

import anyio
import jwt
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, Response

ISSUER = "https://api.cursor.com"
AUDIENCE = "https://teamnebula.ai/claudemem-cursor"
REPOSITORY = re.compile(r"github\.com/teamnebula-ai/[a-z0-9._-]+")
REQUIRED = ["sub", "iat", "nbf", "exp", "jti", "iss", "aud", "cloud_agent_id"]


def validate_snapshot(source, allowed=None):
    if not isinstance(source, dict) or not source or (allowed is not None and set(source) != allowed):
        raise ValueError("Publication repository scope must match the allowlist.")
    ids = set()
    for repo, records in source.items():
        if not REPOSITORY.fullmatch(repo) or not isinstance(records, list) or len(records) > 200:
            raise ValueError("Invalid published repository.")
        for note in records:
            if (
                not isinstance(note, dict) or set(note) != {"id", "title", "narrative"}
                or type(note["id"]) is not int or note["id"] < 1 or note["id"] in ids
                or not isinstance(note["title"], str) or not 1 <= len(note["title"]) <= 180
                or not isinstance(note["narrative"], str) or not 1 <= len(note["narrative"]) <= 16000
            ):
                raise ValueError("Invalid published observation.")
            ids.add(note["id"])
    return {repo: {note["id"]: note for note in notes} for repo, notes in source.items()}


def create_app(owner_id: str, published_file: Path, keys=None, *, store=None, publish_hash=None):
    if not re.fullmatch(r"[0-9]+", owner_id):
        raise ValueError("A verified Cursor owner ID is required.")
    if keys is None:
        keys = jwt.PyJWKClient(ISSUER + "/keys", timeout=5)
    published = validate_snapshot(json.loads(published_file.read_text()))
    allowed_repos = set(published)
    if store is not None and not re.fullmatch(r"[0-9a-f]{64}", publish_hash or ""):
        raise ValueError("A dedicated publication credential digest is required.")

    request_repo = contextvars.ContextVar("request_repo")
    request_notes = contextvars.ContextVar("request_notes")
    mcp = FastMCP(
        "claudemem-teamnebula",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

    @mcp.tool(annotations=read_only)
    def search_notes(query: str, project: str | None = None) -> list[dict]:
        """Search published ClaudeMem notes in the authenticated run's repository."""
        repo = request_repo.get()
        slug = repo.rsplit("/", 1)[1]
        if project is not None and project != slug:
            raise ValueError("Access denied: project outside the authenticated repository.")
        query = query.strip().casefold()
        if not 1 <= len(query) <= 250:
            raise ValueError("Query must be 1 to 250 characters.")
        return [
            {"id": note["id"], "title": note["title"], "project": slug}
            for note in request_notes.get()[repo].values()
            if query in note["title"].casefold() or query in note["narrative"].casefold()
        ][:20]

    @mcp.tool(annotations=read_only)
    def read_note(observation_id: int) -> dict:
        """Read a published ClaudeMem note in the authenticated run's repository."""
        repo = request_repo.get()
        note = request_notes.get()[repo].get(observation_id)
        if note is None:
            raise ValueError("Access denied: observation outside the authenticated repository.")
        return {**note, "project": repo.rsplit("/", 1)[1]}

    def verified_claims(token):
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str) or not 1 <= len(kid) <= 128:
            raise jwt.InvalidTokenError("Invalid signing metadata.")
        claims = jwt.decode(
            token, keys.get_signing_key(kid).key, algorithms=["RS256"],
            audience=AUDIENCE, issuer=ISSUER, leeway=10,
            options={"require": REQUIRED, "strict_aud": True},
        )
        if not all(type(claims[name]) is int for name in ("exp", "iat", "nbf")):
            raise jwt.InvalidTokenError("Invalid claim times.")
        if not 0 < claims["exp"] - claims["iat"] <= 300:
            raise jwt.InvalidTokenError("Invalid token lifetime.")
        return claims

    streamable_http = mcp.streamable_http_app()

    async def publication(scope, receive, send, token):
        if store is None or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), publish_hash):
            await Response(status_code=401)(scope, receive, send)
            return
        try:
            if scope["method"] == "GET":
                data, generation = await anyio.to_thread.run_sync(store.load)
                validate_snapshot(data, allowed_repos)
            elif scope["method"] == "PUT":
                raw = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    raw.extend(message.get("body", b""))
                    if len(raw) > 8_000_000:
                        await Response(status_code=413)(scope, receive, send)
                        return
                    if not message.get("more_body"):
                        break
                body = json.loads(raw)
                if not isinstance(body, dict) or set(body) != {"snapshot", "generation"}:
                    raise ValueError("Invalid publication envelope.")
                data, generation = body["snapshot"], body["generation"]
                validate_snapshot(data, allowed_repos)
                if not isinstance(generation, str) or not generation.isdecimal():
                    raise ValueError("Invalid generation.")
                try:
                    generation = await anyio.to_thread.run_sync(store.replace, data, generation)
                except ValueError:
                    await Response(status_code=409)(scope, receive, send)
                    return
            else:
                await Response(status_code=405)(scope, receive, send)
                return
            digest = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            await JSONResponse({"generation": generation, "digest": digest, "notes": sum(map(len, data.values()))})(scope, receive, send)
        except (ValueError, TypeError, KeyError):
            await Response(status_code=400)(scope, receive, send)
        except Exception:
            await Response(status_code=503)(scope, receive, send)

    async def authenticate(scope, receive, send):
        if scope["type"] != "http":
            await streamable_http(scope, receive, send)
            return
        headers = Headers(scope=scope)
        if "origin" in headers:
            await Response(status_code=403)(scope, receive, send)
            return
        prefix, _, token = headers.get("authorization", "").partition(" ")
        if prefix.lower() != "bearer" or not 1 <= len(token) <= 8192:
            await Response(status_code=401)(scope, receive, send)
            return
        if scope["path"] == "/publication":
            await publication(scope, receive, send, token)
            return
        try:
            claims = await anyio.to_thread.run_sync(verified_claims, token)
        except jwt.PyJWKClientConnectionError:
            await Response(status_code=503)(scope, receive, send)
            return
        except jwt.PyJWTError:
            await Response(status_code=401)(scope, receive, send)
            return
        repos = claims.get("repo_urls")
        repo = claims.get("repo_url")
        if (
            claims.get("team_id") is not None
            or claims.get("owner_user_id") != owner_id
            or claims.get("sub") != f"user:{owner_id}"
            or claims.get("agent_runtime") != "managed"
            or type(claims.get("repo_count")) is not int
            or claims["repo_count"] != 1
            or not isinstance(repo, str)
            or repos != [repo]
            or repo.lower() not in allowed_repos
        ):
            await Response(status_code=403)(scope, receive, send)
            return
        current = published
        if store is not None:
            try:
                data, _ = await anyio.to_thread.run_sync(store.load)
                current = validate_snapshot(data, allowed_repos)
            except Exception:
                await Response("Published memory is unavailable.", status_code=503)(scope, receive, send)
                return
        reset = request_repo.set(repo.lower())
        reset_notes = request_notes.set(current)
        try:
            await streamable_http(scope, receive, send)
        finally:
            request_repo.reset(reset)
            request_notes.reset(reset_notes)

    return TrustedHostMiddleware(
        authenticate, allowed_hosts=["testserver", "127.0.0.1", "localhost", "*.run.app"],
        www_redirect=False,
    )


if __name__ == "__main__":
    from cloud_snapshot import CloudSnapshot
    snapshot = CloudSnapshot(os.environ["CMEM_PUBLICATION_BUCKET"], "published.json")
    app = create_app(os.environ["CURSOR_OWNER_ID"], Path(__file__).with_name("published.json"),
                     store=snapshot, publish_hash=os.environ["CMEM_PUBLISH_TOKEN_SHA256"])
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), access_log=False)
