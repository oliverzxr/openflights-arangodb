# OpenFlights Route Graph

Explore a historical airline network in ArangoDB. Starting in Maceió (MCZ), the project finds direct destinations, adds destinations reached in exactly two route segments, and returns one minimum-hop path to Lisbon. It pairs AQL queries with a Python data pipeline and independent checks on the results.

Developed for the Database Systems course at the Federal University of Alagoas (UFAL).

## Results from the pinned dataset

| Measure | Observed result |
|---|---:|
| Airport vertices | 7,698 |
| Route edges | 66,759 |
| Airline documents | 6,161 |
| Direct destinations from MCZ | 7 |
| Additional destinations in exactly two segments | 114 |
| One minimum-hop path from MCZ to LIS | MCZ → VCP → LIS |
| Most distinct outgoing destinations | FRA (239) |

Each route edge represents a carrier on a directed airport pair. Parallel edges may represent different carriers serving the same pair. The two-segment count excludes MCZ and airports already reachable directly. A minimum-hop search can choose a different intermediate airport when paths tie. The dataset describes historical connectivity. Current schedules, service frequency, and commercial availability require other sources. [Query outputs](docs/evidence.json) · [Analysis and limitations](docs/kdd.md)

## Run from a fresh clone

Use **Python 3.10+** and **Docker with the Compose plugin**. On Windows, start Docker Desktop in Linux-container mode. The Python commands use the standard library. On Linux, use `python3` if `python` is unavailable.

```sh
git clone https://github.com/oliverzxr/openflights-arangodb.git
cd openflights-arangodb
python --version
docker version
docker compose version
```

Create a local `.env` from the repository root. The command generates a random password and stops if the file already exists. The default host port is 8529. If a database volume already exists, its original password still applies.

```sh
python -c "from pathlib import Path; import secrets; p=Path('.env'); p.open('x',encoding='utf-8').write('ARANGO_ROOT_PASSWORD='+secrets.token_hex(24)+'\nARANGO_PORT=8529\n')"
docker compose config --quiet
docker compose up -d --wait
python -m openflights_graph version
```

Compose starts a single ArangoDB 3.12.13 instance bound to local loopback. To use an existing Linux installation instead, configure the same server credentials in `.env` and start at the version check. [Linux installation, backup, and troubleshooting](docs/setup.md)

Download and check the original files against their pinned SHA-256 hashes. Prepare the snapshot, import it, and compare every stored document with the transformed data.

```sh
python -m openflights_graph download
python -m openflights_graph prepare
python -m openflights_graph import
python -m openflights_graph verify
python -m openflights_graph check-queries --output data/aql-results.json
```

The import creates the `openflights` database, its collections, indexes, and the `flight_network` named graph. A repeat import uses stable document keys and ignores existing ones. Compare the expected counts above with the `verify` output. To compute statistics without a running database, use `python -m openflights_graph analyze` after `prepare`.

## Explore the graph and run the CRUD demo

Open [the local ArangoDB interface](http://127.0.0.1:8529), sign in as `root` with the password in `.env`, and select `openflights`. In **Queries**, run the example below with the bind variables `{"origin":"airports/2590"}`. The CLI equivalent is `python -m openflights_graph query 02_direct_destinations`.

```aql
FOR airport IN 1..1 OUTBOUND @origin GRAPH "flight_network"
  COLLECT key = airport._key, iata = airport.iata, city = airport.city
    WITH COUNT INTO carrierEdges
  SORT iata, key
  RETURN { key, iata, city, carrierEdges }
```

Run the isolated write demonstration with `python -m openflights_graph demo`. It seeds `openflights_demo` with real airports and routes, creates and reads a marked terminal and route, updates the terminal, then removes the two demonstration records and verifies the original sample. [Query catalog and CRUD steps](docs/queries.md)

## Tests and execution evidence

Run `python -m unittest discover -s tests -v` for the unit tests. After a successful import, enable the two live integration tests in your shell.

**PowerShell**

```powershell
$env:ARANGO_INTEGRATION='1'
python -m unittest discover -s tests -v
Remove-Item Env:ARANGO_INTEGRATION
```

**Bash**

```bash
ARANGO_INTEGRATION=1 python -m unittest discover -s tests -v
```

The recorded end-to-end test ran against the official ArangoDB 3.12.13 server in a temporary Linux VM. It covered repeat import, all six analytical queries, CRUD through the CLI and Web UI, backup and restore, and ten passing tests. The Windows check covered `docker compose config --quiet`. Running the full Compose lifecycle on Windows is still unverified. Use `docker compose stop` to stop the service while keeping its volume. [Validation record](docs/validation.md)

## Data model and attribution

```mermaid
flowchart LR
    Input["Pinned OpenFlights CSVs"] --> ETL["Python ETL and integrity checks"]
    ETL --> Graph[("ArangoDB")]
    Graph --> AQL["AQL traversal and aggregation"]
    ETL --> Check["Independent Python cross-check"]
    AQL --> Check
```

The named graph connects `airports` vertices through `routes` edges. The `airlines` collection supplies optional carrier metadata. An index supports filtering by country and IATA code, and a unique index enforces one edge for each origin, destination and carrier. [Model and indexes](docs/model.md)

Airport, airline, and route data comes from **OpenFlights**, including historical route records from **Airline Route Mapper**. The database is licensed under **ODbL 1.0** and its individual contents under **DbCL 1.0**. Route updates from the source ceased in June 2014. The downloader fetches three files at a fixed upstream revision and verifies their checksums. Raw files, processed data, and database dumps are generated locally. [OpenFlights data](https://openflights.org/data) · [Upstream license notice](https://raw.githubusercontent.com/jpatokal/openflights/3b0e4d82e0f1c660c706c92bc00dec608a7d8eab/data/LICENSE) · [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) · [DbCL 1.0](https://opendatacommons.org/licenses/dbcl/1-0/)

## Repository layout

| Path | Purpose |
|---|---|
| `openflights_graph/` | Downloader, ETL, ArangoDB HTTP client, and CLI |
| `queries/analysis/` | Filters, traversals, aggregation, shortest path, and integrity audit |
| `queries/crud/` | Isolated CRUD and verification |
| `tests/` | Unit and opt-in live integration tests |
| `docs/` | Setup, data provenance, analysis, and execution evidence |

## Contributors

Rodrigo Oliveira Calaça, Davy Caetano Nascimento, and Vitor Pascoal Alves.
