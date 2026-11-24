# OpenFlights Route Graph

A reproducible ArangoDB lab for asking a local question about a historical air transport network. Which airports can be reached from Maceió (MCZ) in one or two route segments, and which airports connect to the most distinct destinations?

Built for the Database Systems AB2 assessment at the Federal University of Alagoas (UFAL).

## Model and pipeline

```mermaid
flowchart LR
    Input["Pinned OpenFlights CSVs"] --> Python["Python ETL and integrity checks"]
    Python --> Graph[("ArangoDB 3.12.13")]
    Graph --> AQL["AQL traversal, aggregation and path search"]
    Python --> Check["Independent Python cross-check"]
    AQL --> Check
```

Each `airports` document is a vertex. Each `routes` edge connects two airports in one direction and represents a carrier listing. Multiple carriers can connect the same ordered pair. `airlines` provides optional carrier attributes. The named graph is `flight_network`. [Data model and indexes](docs/model.md).

## Run locally

Requires Python 3.10+ and Docker Compose. The Python commands use the standard library. Create a local `.env` with a strong, random, unquoted `ARANGO_ROOT_PASSWORD` before starting. The default port is 8529. The [Windows and Linux setup guide](docs/setup.md) includes credential creation, a Docker-free alternative, the Web UI, backup and restore, and troubleshooting.

```sh
docker compose up -d --wait
python -m openflights_graph download
python -m openflights_graph prepare
python -m openflights_graph import
python -m openflights_graph verify
python -m openflights_graph analyze
python -m openflights_graph check-queries --output data/aql-results.json
python -m unittest discover -s tests -v
```

For integration tests, set `ARANGO_INTEGRATION=1` in the current shell after a successful import, then rerun the test command. The import compares all stored documents with the transformed snapshot. A repeat import uses stable keys and ignores existing records. Use `docker compose stop` to stop the local service.

The full workflow ran on the official 3.12.13 server in a temporary Linux VM. The checks covered repeat import, the six analytical queries, CRUD and dump/restore. Compose configuration was validated separately. [Validation record](docs/validation.md).

## Example AQL

Find direct destinations and count the listed carrier edges per destination. Set the bind parameter `origin` to `airports/2590` for MCZ.

```aql
FOR airport IN 1..1 OUTBOUND @origin GRAPH "flight_network"
  COLLECT key = airport._key, iata = airport.iata, city = airport.city
    WITH COUNT INTO carrierEdges
  SORT iata, key
  RETURN { key, iata, city, carrierEdges }
```

The [query catalog](docs/queries.md) covers filters, two-hop-only destinations, outgoing hubs, minimum-hop paths and the integrity audit. To run the write sequence in an isolated database seeded from two real airports and their routes, use `python -m openflights_graph demo`. The added terminal and edge are labeled demonstration data.

## Findings and data attribution

The ETL retained **7,698 airport vertices**, **66,759 route edges** and **6,161 auxiliary airline documents**. Maceió has **7 direct destinations** and **114 additional destinations reachable in exactly two hops**. The largest observed outbound destination set was Frankfurt (FRA) with **239** distinct airports. [Methods and limitations](docs/kdd.md) · [Python results](docs/python-results.json).

Airport, airline and route data comes from [OpenFlights](https://openflights.org/data), including historical route listings supplied by Airline Route Mapper. The database is under ODbL 1.0 and its contents under DbCL 1.0. Route updates ceased in June 2014. Paths show the structure of a historical network. Schedule compatibility, fares, frequency and traffic volume are outside the source’s scope. Inputs and generated databases are downloaded or produced locally. [Dataset selection and license](docs/datasets.md).

## Repository

| Path | Purpose |
|---|---|
| `openflights_graph/` | ETL, HTTP client, import, validation and CLI |
| `queries/analysis/`, `queries/crud/` | Read-only AQL and isolated writes |
| `tests/` | Unit and opt-in live integration tests |
| `docs/` | Installation, model, query catalog and results |

## Contributors

Rodrigo Oliveira Calaça, Davy Caetano Nascimento and Vitor Pascoal Alves.
