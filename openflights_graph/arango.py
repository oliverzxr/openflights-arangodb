"""Minimal client for the ArangoDB HTTP endpoints used by the lab."""
import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .dataset import COLLECTIONS, ROOT, validate_collections

MAIN = "openflights"
DEMO = "openflights_demo"
GRAPH = "flight_network"
EDGE_DEFINITION = {"collection": "routes", "from": ["airports"], "to": ["airports"]}
BATCH_SIZE = 2_000


class ArangoError(RuntimeError):
    def __init__(self, method, path, status, payload):
        self.status = status
        self.error_num = payload.get("errorNum")
        detail = payload.get("errorMessage", "Unexpected error")
        super().__init__(f"{method} {path}: HTTP {status}, ArangoDB {self.error_num}: {detail}")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def settings():
    values = {}
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, separator, value = stripped.partition("=")
            if not separator:
                raise ValueError(f"Missing '=' in .env entry: {key}")
            values[key.strip()] = value.strip()
    for key in ("ARANGO_PORT", "ARANGO_URL", "ARANGO_USER", "ARANGO_ROOT_PASSWORD", "ARANGO_PASSWORD"):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


class Client:
    def __init__(self, base_url, user, password):
        url = urlsplit(base_url)
        if (
            not url.hostname or url.path not in ("", "/") or url.query or url.fragment
            or url.username is not None
        ):
            raise ValueError("ARANGO_URL must be a base server URL without embedded credentials")
        if url.scheme != "https" and (
            url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Plain HTTP is allowed only on loopback")
        self.base_url = base_url.rstrip("/")
        self.auth = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        self.opener = build_opener(NoRedirect())

    @classmethod
    def from_environment(cls):
        config = settings()
        user = config.get("ARANGO_USER", "root")
        password = config.get("ARANGO_PASSWORD")
        if password is None and user == "root":
            password = config.get("ARANGO_ROOT_PASSWORD")
        if not password:
            raise ValueError("Set ARANGO_ROOT_PASSWORD for root or ARANGO_PASSWORD for another user")
        url = config.get("ARANGO_URL", f"http://127.0.0.1:{config.get('ARANGO_PORT', '8529')}")
        return cls(url, user, password)

    def request(self, method, database, path, body=None, params=None):
        url = f"{self.base_url}/_db/{quote(database, safe='')}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        content = None if body is None else json.dumps(body, allow_nan=False).encode("utf-8")
        request = Request(url, content, method=method, headers={
            "Authorization": f"Basic {self.auth}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        try:
            with self.opener.open(request, timeout=90) as response:
                return json.load(response)
        except HTTPError as error:
            with error:
                try:
                    payload = json.load(error)
                except (UnicodeError, ValueError):
                    payload = {}
            raise ArangoError(method, path, error.code, payload) from None
        except URLError as error:
            raise RuntimeError(f"Cannot reach ArangoDB at {self.base_url}: {error.reason}") from None

    def query(self, database, aql, bind=None):
        cursor = self.request("POST", database, "/_api/cursor", {
            "query": aql, "bindVars": bind or {}, "batchSize": BATCH_SIZE,
        })
        result = cursor["result"]
        while cursor["hasMore"]:
            cursor = self.request("POST", database, f"/_api/cursor/{cursor['id']}")
            result.extend(cursor["result"])
        return result

    def version(self):
        return self.request("GET", "_system", "/_api/version")


def ignore_duplicate(action):
    try:
        action()
    except ArangoError as error:
        if error.error_num != 1207:
            raise


def setup(client, database):
    if database not in client.request("GET", "_system", "/_api/database")["result"]:
        ignore_duplicate(lambda: client.request("POST", "_system", "/_api/database", {"name": database}))
    existing = {
        col["name"]: col["type"] for col in client.request("GET", database, "/_api/collection")["result"]
    }
    for name in COLLECTIONS:
        expected_type = 3 if name == "routes" else 2
        if name not in existing:
            ignore_duplicate(lambda: client.request("POST", database, "/_api/collection", {
                "name": name, "type": expected_type,
            }))
        metadata = client.request("GET", database, f"/_api/collection/{name}")
        if metadata["type"] != expected_type:
            raise ValueError(f"Collection type mismatch for {database}/{name}")

    graphs = client.request("GET", database, "/_api/gharial")["graphs"]
    if GRAPH not in {graph["name"] if "name" in graph else graph["_key"] for graph in graphs}:
        ignore_duplicate(lambda: client.request("POST", database, "/_api/gharial", {
            "name": GRAPH, "edgeDefinitions": [EDGE_DEFINITION],
        }))
    graph = client.request("GET", database, f"/_api/gharial/{GRAPH}")["graph"]
    if graph["edgeDefinitions"] != [EDGE_DEFINITION] or graph["orphanCollections"]:
        raise ValueError(f"Unexpected definition for graph {database}/{GRAPH}")

    for collection, fields, unique in (
        ("airports", ["country", "iata"], False),
        ("routes", ["_from", "_to", "carrier"], True),
    ):
        client.request("POST", database, "/_api/index", {
            "type": "persistent", "fields": fields, "unique": unique,
        }, params={"collection": collection})


def import_collections(client, database, data):
    validate_collections(data)
    receipts = {}
    for name in COLLECTIONS:
        documents = data[name]
        totals = dict.fromkeys(("created", "ignored"), 0)
        for offset in range(0, len(documents), BATCH_SIZE):
            batch = documents[offset:offset + BATCH_SIZE]
            result = client.request("POST", database, "/_api/import", batch, params={
                "collection": name, "type": "array", "onDuplicate": "ignore",
                "complete": "true", "details": "true",
            })
            if result["errors"] or result["created"] + result["ignored"] != len(batch):
                raise RuntimeError(f"Import failed in {name}, batch starting at {offset}: {result}")
            for count in totals:
                totals[count] += result[count]
        receipts[name] = totals
    return receipts


def verify(client, database, data):
    counts = {}
    for name in COLLECTIONS:
        actual = client.query(database, """
            FOR doc IN @@collection
              RETURN UNSET(doc, "_rev", "_id")
        """, {"@collection": name})
        expected = {doc["_key"]: doc for doc in data[name]}
        if len(actual) != len(expected):
            raise ValueError(f"{database}/{name}: expected {len(expected)} documents, found {len(actual)}")
        for doc in actual:
            if doc != expected.get(doc["_key"]):
                raise ValueError(f"{database}/{name}: unexpected data at {doc['_key']}")
        counts[name] = len(actual)
    return counts
