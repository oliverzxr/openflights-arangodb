"""Fetch and transform a pinned OpenFlights snapshot."""
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SNAPSHOT = ROOT / "data" / "snapshot.json"
REVISION = "3b0e4d82e0f1c660c706c92bc00dec608a7d8eab"
URL = f"https://raw.githubusercontent.com/jpatokal/openflights/{REVISION}/data"
HASHES = {
    "airports.dat": "9387cdb38df5bd664da823f8ccb69fdd9b33a1888f5b7cca09c34a3cd9ff59f9",
    "airlines.dat": "39be1a432e8b04ebc12860c29281c974a9cb52169c82b2456a835d66ab1548a1",
    "routes.dat": "bd373706238134f619c624c606dccc74c05c2582a977c489c81de501735f2390",
}
COLLECTIONS = ("airports", "airlines", "routes")


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def write_atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        destination = Path(temporary.name)
        try:
            temporary.write(content)
            temporary.close()
            os.replace(destination, path)
        finally:
            temporary.close()
            destination.unlink(missing_ok=True)


def write_json(path, value):
    content = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
    write_atomic(path, (content + "\n").encode("utf-8"))


def verify_raw(directory):
    for name, expected in HASHES.items():
        path = directory / name
        if sha256(path.read_bytes()) != expected:
            raise ValueError(f"SHA-256 mismatch: {path}")


def download(directory):
    for name, expected in HASHES.items():
        path = directory / name
        if not path.exists():
            with urlopen(f"{URL}/{name}", timeout=45) as source:
                content = source.read()
            if sha256(content) != expected:
                raise ValueError(f"Unexpected download checksum: {name}")
            write_atomic(path, content)
    verify_raw(directory)


def optional(value):
    value = value.strip()
    return None if value in {"", r"\N", "-", "N/A"} else value


def positive_id(value):
    return str(int(value)) if value.isascii() and value.isdecimal() and int(value) > 0 else None


def rows(path, fields, counts):
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.reader(stream, strict=True):
            counts["original"] += 1
            if len(row) != fields:
                counts["bad_width"] += 1
                continue
            yield row


def read_catalog(path, width, build):
    counts = Counter()
    documents = {}
    for row in rows(path, width, counts):
        key = positive_id(row[0])
        if not key or not optional(row[1]):
            counts["invalid_id_or_name"] += 1
            continue
        if key in documents:
            counts["duplicate_id"] += 1
            continue
        documents[key] = build(key, row)
    counts["retained"] = len(documents)
    return documents, dict(counts)


def airport(key, row):
    lat, lon = (float(value) if optional(value) else None for value in row[6:8])
    if (lat is not None and not -90 <= lat <= 90) or (lon is not None and not -180 <= lon <= 180):
        raise ValueError(f"Invalid coordinates at airport {key}")
    return {
        "_key": key, "name": row[1].strip(), "city": optional(row[2]),
        "country": optional(row[3]), "iata": optional(row[4]),
        "icao": optional(row[5]), "latitude": lat, "longitude": lon,
    }


def airline(key, row):
    return {
        "_key": key, "name": row[1].strip(), "iata": optional(row[3]),
        "icao": optional(row[4]), "country": optional(row[6]),
        "active_in_catalog": {"Y": True, "N": False}.get(row[7]),
    }


def read_routes(path, airports, airlines):
    counts = Counter()
    routes = {}
    for row in rows(path, 9, counts):
        code, raw_carrier, _, origin_id, _, destination_id, codeshare, stops, planes = row
        origin = positive_id(origin_id)
        destination = positive_id(destination_id)
        if not origin or not destination:
            counts["missing_airport_id"] += 1
            continue
        if origin not in airports or destination not in airports:
            counts["unknown_airport_id"] += 1
            continue
        if origin == destination:
            counts["self_loop"] += 1
            continue
        if stops != "0":
            counts["nonstop_filter"] += 1
            continue
        if codeshare not in {"", "Y"}:
            counts["invalid_codeshare"] += 1
            continue
        carrier_id = positive_id(raw_carrier)
        code = optional(code)
        if not carrier_id and not code:
            counts["missing_carrier"] += 1
            continue
        carrier = f"id:{carrier_id}" if carrier_id else f"code:{code}"
        identity = (origin, destination, carrier)
        if identity in routes:
            counts["merged_rows"] += 1
        air_key = carrier_id if carrier_id in airlines else None
        edge = routes.setdefault(identity, {
            "_key": sha256(json.dumps(identity).encode("ascii"))[:32],
            "_from": f"airports/{origin}", "_to": f"airports/{destination}",
            "carrier": carrier, "airline_id": air_key, "airline_codes": set(),
            "codeshares": set(), "equipment": set(),
        })
        if code:
            edge["airline_codes"].add(code)
        edge["codeshares"].add(codeshare == "Y")
        edge["equipment"].update(planes.split() if optional(planes) else [])

    for edge in routes.values():
        for attribute in ("airline_codes", "codeshares", "equipment"):
            edge[attribute] = sorted(edge[attribute])
    counts["retained"] = len(routes)
    return list(routes.values()), dict(counts)


def validate_collections(collections):
    if set(collections) != set(COLLECTIONS):
        raise ValueError("Unexpected snapshot collections")
    keys = {}
    for name, documents in collections.items():
        keys[name] = {doc["_key"] for doc in documents}
        if not keys[name] or len(keys[name]) != len(documents):
            raise ValueError(f"Empty collection or duplicate _key: {name}")
    airport_ids = {f"airports/{key}" for key in keys["airports"]}
    identities = set()
    for edge in collections["routes"]:
        identity = (edge["_from"], edge["_to"], edge["carrier"])
        origin, destination, _ = identity
        if origin not in airport_ids or destination not in airport_ids or origin == destination:
            raise ValueError(f"Invalid endpoint in route {edge['_key']}")
        if edge["airline_id"] is not None and edge["airline_id"] not in keys["airlines"]:
            raise ValueError(f"Unknown airline reference in route {edge['_key']}")
        if identity in identities:
            raise ValueError(f"Duplicate route identity: {identity}")
        identities.add(identity)


def transform(directory):
    airports, airport_counts = read_catalog(directory / "airports.dat", 14, airport)
    airlines, airline_counts = read_catalog(directory / "airlines.dat", 8, airline)
    routes, route_counts = read_routes(directory / "routes.dat", airports, airlines)
    collections = {"airports": list(airports.values()), "airlines": list(airlines.values()), "routes": routes}
    validate_collections(collections)
    return {
        "revision": REVISION, "sha256": HASHES, "collections": collections,
        "counts": {"airports": airport_counts, "airlines": airline_counts, "routes": route_counts},
    }


def load_snapshot(path):
    with path.open(encoding="utf-8") as stream:
        snapshot = json.load(stream)
    if snapshot["revision"] != REVISION or snapshot["sha256"] != HASHES:
        raise ValueError("Snapshot source differs from the pinned inputs")
    validate_collections(snapshot["collections"])
    for name, documents in snapshot["collections"].items():
        counts = snapshot["counts"][name]
        if counts["retained"] != len(documents):
            raise ValueError(f"Invalid retained count in {name}")
        if counts["original"] != sum(count for key, count in counts.items() if key != "original"):
            raise ValueError(f"Original count does not match ETL outcomes in {name}")
    return snapshot
