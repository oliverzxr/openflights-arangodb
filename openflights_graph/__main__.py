"""Commands for data preparation, ingestion, querying and the live demo."""
import argparse
import json
import sys
from pathlib import Path

from .analysis import analyze
from .arango import DEMO, MAIN, Client, import_collections, setup, verify
from .dataset import RAW, ROOT, SNAPSHOT, download, load_snapshot, transform, verify_raw, write_json

ORIGIN = {"origin": "airports/2590"}
QUERIES = {
    "01_brazil_airports": {"country": "Brazil", "iata_min": "S"},
    "02_direct_destinations": ORIGIN,
    "03_two_hops_only": ORIGIN,
    "04_top_hubs": {},
    "05_shortest_path": {**ORIGIN, "destination": "airports/1638"},
    "06_integrity": {},
}
CRUD = ("01_create", "02_read", "03_update", "04_delete", "05_verify")


def run_query(client, group, name, database, bind=None):
    source = ROOT / "queries" / group / f"{name}.aql"
    return client.query(database, source.read_text(encoding="utf-8"), bind)


def demo_seed(data):
    airports = {"2590", "2564"}
    handles = {f"airports/{key}" for key in airports}
    edges = [
        route for route in data["routes"]
        if route["_from"] in handles and route["_to"] in handles
    ]
    airlines = {route["airline_id"] for route in edges}
    return {
        "airports": [doc for doc in data["airports"] if doc["_key"] in airports],
        "airlines": [doc for doc in data["airlines"] if doc["_key"] in airlines],
        "routes": edges,
    }


def prepare_demo(client, data):
    seed = demo_seed(data)
    setup(client, DEMO)
    receipts = import_collections(client, DEMO, seed)
    state = run_query(client, "crud", "05_verify", DEMO)[0]
    if state["airport"] is not None or state["route"] is not None:
        raise ValueError("Previous demo is still present. Run its guarded delete step before retrying.")
    return {"database": DEMO, "import": receipts, "verified": verify(client, DEMO, seed)}


def run_demo(client, data):
    prepared = prepare_demo(client, data)
    results = {step: run_query(client, "crud", step, DEMO) for step in CRUD}
    stage = results["03_update"]
    if (
        len(results["01_create"]) != 1 or len(results["02_read"]) != 1
        or len(stage) != 1 or stage[0]["stage"] != "updated"
        or results["04_delete"] != [{"deletedAirport": "demo_terminal", "deletedRoute": "demo_route"}]
        or results["05_verify"] != [{"airport": None, "route": None, "seed": ["MCZ", "GRU"]}]
    ):
        raise ValueError(f"Unexpected demo results: {results}")
    return {"prepared": prepared, "steps": results, "verified_after": verify(client, DEMO, demo_seed(data))}


def analyze_server(client, snapshot):
    evidence = {
        name: run_query(client, "analysis", name, MAIN, bind)
        for name, bind in QUERIES.items()
    }
    python = analyze(snapshot)
    direct = evidence["02_direct_destinations"]
    two_hops = evidence["03_two_hops_only"]
    path = evidence["05_shortest_path"]
    routes = snapshot["collections"]["routes"]
    pairs = {(edge["_from"], edge["_to"]) for edge in routes}
    handles = [f"airports/{airport['key']}" for airport in path]
    integrity = evidence["06_integrity"]
    expected_integrity = {name: len(docs) for name, docs in snapshot["collections"].items()}
    expected_integrity.update(invalid_routes=0, duplicated_identities=0)
    if sorted(d["iata"] or f"airports/{d['key']}" for d in direct) != python["maceio"]["direct"]:
        raise ValueError("AQL and Python disagree on direct destinations")
    if len(two_hops) != python["maceio"]["two_hops_only_count"] or [
        {"key": d["key"], "iata": d["iata"], "connections": d["viaCount"]} for d in two_hops[:10]
    ] != python["maceio"]["most_alternatives"]:
        raise ValueError("AQL and Python disagree on indirect destinations")
    if evidence["04_top_hubs"] != python["top_outbound"] or integrity != [expected_integrity]:
        raise ValueError("Hub or integrity audit differs from the imported snapshot")
    if (
        not handles or handles[0] != ORIGIN["origin"] or handles[-1] != "airports/1638"
        or any(pair not in pairs for pair in zip(handles, handles[1:]))
        or len(handles) != 3 or (handles[0], handles[-1]) in pairs
    ):
        raise ValueError("Unexpected minimum-hop itinerary in pinned data")
    if evidence["01_brazil_airports"] == []:
        raise ValueError("Brazilian airport filter should return records")
    if run_query(client, "analysis", "01_brazil_airports", MAIN,
                 {"country": "__no_such_country__", "iata_min": "S"}) != []:
        raise ValueError("Expected no rows for a non-existent country")
    return {"server": client.version(), "queries": evidence, "python_cross_check": "passed",
            "empty_filter": []}


def arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("download", "prepare", "version", "import", "demo-seed"):
        sub.add_parser(command)
    sub.add_parser("verify").add_argument("--database", default=MAIN)
    for command in ("analyze", "check-queries", "demo"):
        sub.add_parser(command).add_argument("--output", type=Path)
    query = sub.add_parser("query")
    query.add_argument("name", choices=QUERIES)
    query.add_argument("--bind", type=json.loads)
    sub.add_parser("demo-step").add_argument("name", choices=CRUD)
    return parser.parse_args(argv)


def execute(args):
    command = args.command
    if command == "download":
        download(RAW)
        return {"directory": str(RAW), "checksums": "verified"}
    if command == "prepare":
        verify_raw(RAW)
        snapshot = transform(RAW)
        write_json(SNAPSHOT, snapshot)
        return {"snapshot": str(SNAPSHOT), "counts": snapshot["counts"]}
    if command == "analyze":
        return analyze(load_snapshot(SNAPSHOT))

    client = Client.from_environment()
    if command == "version":
        return client.version()
    if command == "query":
        bind = args.bind if args.bind is not None else QUERIES[args.name]
        if not isinstance(bind, dict):
            raise ValueError("--bind must be a JSON object")
        return run_query(client, "analysis", args.name, MAIN, bind)
    if command == "demo-step":
        return run_query(client, "crud", args.name, DEMO)

    snapshot = load_snapshot(SNAPSHOT)
    data = snapshot["collections"]
    if command == "import":
        setup(client, MAIN)
        receipt = import_collections(client, MAIN, data)
        return {"server": client.version(), "import": receipt, "verified": verify(client, MAIN, data)}
    if command == "verify":
        return {"database": args.database, "verified": verify(client, args.database, data)}
    if command == "check-queries":
        return analyze_server(client, snapshot)
    if command == "demo-seed":
        return prepare_demo(client, data)
    return run_demo(client, data)


def main(argv=None):
    args = arguments(argv)
    try:
        result = execute(args)
        output = getattr(args, "output", None)
        if output:
            write_json(output, result)
            return 0
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
