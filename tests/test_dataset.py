import csv
import tempfile
import unittest
from pathlib import Path

from openflights_graph.dataset import load_snapshot, transform, validate_collections, write_json


class DatasetTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.directory = Path(work.name)
        airport = lambda key, iata: [key, f"Airport {key}", "City", "Brazil", iata, r"\N",
                                     -9, -35, 0, -3, "N", "UTC", "airport", "fixture"]
        self.write("airports.dat", [airport(1, "MCZ"), airport(2, "GRU"), airport(1, "DUP")])
        self.write("airlines.dat", [[7, "Carrier", r"\N", "X1", "XXX", "", "Brazil", "Y"]])
        good = ["X1", 7, "MCZ", 1, "GRU", 2, "", 0, "738"]
        self.write("routes.dat", [
            good, [*good[:6], "Y", 0, "320"],
            [*good[:5], r"\N", "", 0, "738"],
            [*good[:5], 200, "", 0, "738"],
            [*good[:5], 1, "", 0, "738"],
            [*good[:7], 1, "738"],
            ["invalid width"],
        ])

    def write(self, name, rows):
        with (self.directory / name).open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerows(rows)

    def test_normalize_merge_filter_and_account(self):
        result = transform(self.directory)
        counts = result["counts"]
        self.assertEqual(counts["airports"], {"original": 3, "duplicate_id": 1, "retained": 2})
        self.assertEqual(counts["routes"], {
            "original": 7, "merged_rows": 1, "missing_airport_id": 1, "unknown_airport_id": 1,
            "self_loop": 1, "nonstop_filter": 1, "bad_width": 1, "retained": 1,
        })
        edge, = result["collections"]["routes"]
        self.assertEqual((edge["_from"], edge["_to"]), ("airports/1", "airports/2"))
        self.assertEqual(edge["equipment"], ["320", "738"])
        self.assertEqual(edge["codeshares"], [False, True])
        self.assertEqual(edge["airline_id"], "7")
        self.assertIsNone(result["collections"]["airports"][0]["icao"])

    def test_reexecution_is_deterministic(self):
        self.assertEqual(transform(self.directory), transform(self.directory))

    def test_missing_file_is_reported(self):
        (self.directory / "routes.dat").unlink()
        with self.assertRaises(FileNotFoundError):
            transform(self.directory)

    def test_invalid_endpoint_blocks_import_before_writes(self):
        collections = transform(self.directory)["collections"]
        collections["routes"][0]["_to"] = "airports/999"
        with self.assertRaisesRegex(ValueError, "Invalid endpoint"):
            validate_collections(collections)

    def test_duplicate_route_identity_is_rejected_even_with_different_key(self):
        collections = transform(self.directory)["collections"]
        collections["routes"].append({**collections["routes"][0], "_key": "another"})
        with self.assertRaisesRegex(ValueError, "Duplicate route identity"):
            validate_collections(collections)

    def test_snapshot_has_matching_counts(self):
        path = self.directory / "snapshot.json"
        data = transform(self.directory)
        write_json(path, data)
        self.assertEqual(load_snapshot(path), data)
        data["counts"]["routes"]["original"] += 1
        write_json(path, data)
        with self.assertRaisesRegex(ValueError, "Original count"):
            load_snapshot(path)
