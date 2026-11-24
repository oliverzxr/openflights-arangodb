import os
import unittest
from unittest.mock import Mock

from openflights_graph.__main__ import analyze_server, demo_seed, run_demo
from openflights_graph.arango import DEMO, GRAPH, MAIN, ArangoError, Client, import_collections, verify
from openflights_graph.dataset import SNAPSHOT, load_snapshot


class ImportTests(unittest.TestCase):
    def test_stop_on_batch_failure(self):
        client = Mock()
        client.request.return_value = {"errors": 1, "created": 0, "ignored": 0}
        data = {
            "airports": [{"_key": "1"}, {"_key": "2"}], "airlines": [{"_key": "7"}],
            "routes": [{"_key": "edge", "_from": "airports/1", "_to": "airports/2",
                        "carrier": "id:7", "airline_id": "7"}],
        }
        with self.assertRaisesRegex(RuntimeError, "airports, batch starting at 0"):
            import_collections(client, MAIN, data)
        self.assertEqual(client.request.call_count, 1)
        self.assertEqual(client.request.call_args.kwargs["params"]["complete"], "true")

    def test_refuse_plain_http_off_loopback(self):
        with self.assertRaisesRegex(ValueError, "only on loopback"):
            Client("http://example.test", "root", "example")


@unittest.skipUnless(os.environ.get("ARANGO_INTEGRATION") == "1", "requires imported ArangoDB")
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = Client.from_environment()
        cls.snapshot = load_snapshot(SNAPSHOT)
        cls.data = cls.snapshot["collections"]

    def test_database_content_and_aql_cross_check(self):
        self.assertEqual(verify(self.client, MAIN, self.data),
                         {name: len(docs) for name, docs in self.data.items()})
        self.assertEqual(analyze_server(self.client, self.snapshot)["python_cross_check"], "passed")

    def test_crud_twice_then_check_invalid_relationship_and_unique_index(self):
        for _ in range(2):
            result = run_demo(self.client, self.data)
            self.assertEqual(result["steps"]["05_verify"],
                             [{"airport": None, "route": None, "seed": ["MCZ", "GRU"]}])
        seed = demo_seed(self.data)
        edge = seed["routes"][0]
        endpoint = f"/_api/gharial/{GRAPH}/edge/routes"
        with self.assertRaises(ArangoError) as invalid:
            self.client.request("POST", DEMO, endpoint, {**edge, "_key": "invalid_test",
                                                        "_to": "airports/missing"})
        self.assertEqual(invalid.exception.error_num, 1202)
        with self.assertRaises(ArangoError) as duplicate:
            self.client.request("POST", DEMO, endpoint, {**edge, "_key": "duplicate_test"})
        self.assertEqual(duplicate.exception.error_num, 1210)
        verify(self.client, DEMO, seed)
        verify(self.client, MAIN, self.data)
