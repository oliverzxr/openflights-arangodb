"""Independent Python analysis of the processed snapshot."""
from collections import Counter, defaultdict


def analyze(snapshot):
    data = snapshot["collections"]
    airports = {f"airports/{doc['_key']}": doc for doc in data["airports"]}
    routes = data["routes"]
    outbound = defaultdict(set)
    inbound = defaultdict(set)
    for edge in routes:
        outbound[edge["_from"]].add(edge["_to"])
        inbound[edge["_to"]].add(edge["_from"])

    def describe(handle):
        return {"key": airports[handle]["_key"], "iata": airports[handle]["iata"]}

    mcz, = (key for key, airport in airports.items() if airport["iata"] == "MCZ")
    direct = outbound[mcz]
    through = defaultdict(set)
    for connection in direct:
        for destination in outbound[connection] - direct - {mcz}:
            through[destination].add(connection)
    hubs = sorted(outbound, key=lambda key: (-len(outbound[key]), key))[:10]
    pairs = sum(map(len, outbound.values()))
    multiplicity = Counter((edge["_from"], edge["_to"]) for edge in routes)
    connected = set(outbound) | set(inbound)
    return {
        "source_revision": snapshot["revision"], "etl": snapshot["counts"],
        "graph": {
            "vertices": len(airports), "edges": len(routes), "directed_pairs": pairs,
            "connected_airports": len(connected), "isolated_airports": len(airports) - len(connected),
            "pairs_with_parallel_edges": sum(total > 1 for total in multiplicity.values()),
            "carrier_edges_per_pair": dict(sorted(Counter(multiplicity.values()).items())),
            "reciprocal_direction_pairs": sum(
                source in outbound.get(destination, ()) for source, destination in multiplicity
            ),
            "edges_with_airline_catalog_match": sum(edge["airline_id"] is not None for edge in routes),
            "codeshare_only_edges": sum(edge["codeshares"] == [True] for edge in routes),
            "non_codeshare_only_edges": sum(edge["codeshares"] == [False] for edge in routes),
            "mixed_codeshare_edges": sum(len(edge["codeshares"]) == 2 for edge in routes),
        },
        "top_outbound": [
            {**describe(key), "destinations": len(outbound[key])} for key in hubs
        ],
        "maceio": {
            "origin": describe(mcz),
            "direct": sorted(airports[key]["iata"] or key for key in direct),
            "two_hops_only_count": len(through),
            "most_alternatives": [
                {**describe(key), "connections": len(through[key])}
                for key in sorted(through, key=lambda key: (-len(through[key]), key))[:10]
            ],
        },
    }
