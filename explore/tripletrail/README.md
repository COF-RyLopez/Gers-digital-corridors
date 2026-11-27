# Exploration: tripletrail for Overture routing

[tripletrail](https://github.com/Matdata-eu/tripletrail) is a Rust RDF triple store (built on
Oxigraph) with SPARQL, GeoSPARQL + PostGIS `ST_*` functions, the pgRouting `pgr_*` function
set, linear referencing and line conflation built in. It is aimed at rail networks, but its
routing only sees edge sets, so it works on any graph we hand it, including Overture
transportation.

This folder is a self-contained experiment. It does not touch the demo, the tagger or the
relay.

## What is here

| Path | What it does |
|---|---|
| `scripts/fetch_overture.py` | Pulls Overture `2026-11-18.0` road segments for a bbox (default: Des Moines + Altoona, I-80/I-35/I-235) with DuckDB, splits each segment at its connectors into routable edges, and writes RDF. Also loads the 37 live 511 events in that box from `demo/data/corridor_events.json`, with the tagger's existing GERS matches. |
| `scripts/explore.py` | Runs every query below against the server and prints a summary; writes `data/route.geojson` and `data/detour.geojson`. |
| `queries/*.rq` | The SPARQL, one file per idea. |
| `map.html` | Leaflet map of the route, the detour and the events (open it from a local `python3 -m http.server` at the repo root). |
| `run.sh` | Build tripletrail, fetch, serve, run, all in one. |
| `data/run.txt` | The output of the run below. |

```sh
cd explore/tripletrail && ./run.sh          # or step by step:
cargo install --locked --path <tripletrail checkout>/crates/tripletrail-server
python3 scripts/fetch_overture.py           # ~10 s, 8.5k segments -> 20k edges, 19k connectors
tripletrail serve --load data/graph.nt --load data/events.nt
python3 scripts/explore.py
```

Setup notes: there is no release or PyPI wheel yet (`pip install tripletrail` finds nothing),
so it builds from source: Rust 1.95+, about 8 minutes on 4 cores, a 445 MB binary with debug
info. The 306k-triple extract loads in 0.3 s.

## How Overture becomes a graph

Overture segments are not graph edges. A segment runs through any number of connectors, each
with an `at` position (0..1). The fetch script cuts every road segment at its connectors, so
each edge goes connector to connector and keeps:

- its parent segment's GERS ID and the `[from_at, to_at]` range it covers,
- length (geodesic), travel time (Overture `speed_limits`, else a per-class default),
- direction: `access_restrictions` with `heading: backward, access_type: denied` makes it one-way
  (6.8k edges in this extract, nearly all divided-highway carriageways and ramps).

So a route comes back as a list of **GERS linear references** (segment ID + range), which is the
same shape as the `location_references` the tagger writes. That is the main fit: routes, events
and segments all speak GERS.

## Results (Des Moines extract, 2026-11-27)

| Idea | Query | Result |
|---|---|---|
| Fastest route | `route.rq` (`pgr_dijkstra`) | I-80 east of Altoona to west Des Moines: 25.6 min, 90 edges on 60 GERS segments. ~100 ms first call, single-digit ms once the graph is cached. |
| Closure-aware detour | `detour.rq` (`rail:route` + `pgr:constraint "!?c_closed"`) | Removing segments matched to live "Closed" 511 events (not "Shoulders Closed") routes off I-80 at Hubbell Ave and back on via I-235: 28.3 min, +2.7 min, 117 segments not on the original route. |
| Who is affected | `upstream_reach.rq` (`pgr_drivingDistance` on the reversed graph) | 4,199 connectors can reach the destination within 10 min: the set of DMS signs, 511 subscribers or fleet vehicles to warn about an event there. |
| Corridor resilience | `bridges.rq` (`pgr_bridges`) | 211 motorway/trunk segments whose loss disconnects the motorway network in the extract. (Not checked by hand: many are likely ramps or cut off by the bbox edge; worth a real look on a whole corridor.) |
| Point event to full linear ref | `linear_ref.rq` (`rail:intrinsicAt`) | All 27 point matches get an `at` on their segment, e.g. `at=0.815, snap 1.2 m`. The tagger today emits only the segment ID. |
| Line event conflation | `conflate_lines.rq` (`rail:conflate`) | Segments at least half covered by the 10 line events: 93 pairs. 72 agree with the tagger's 108, 21 are new (short segments under the tagger's 80 m absolute overlap), 36 are tagger-only (partial or opposite-side hits). |
| **Wrong carriageway** | `direction_check.rq` (`ST_Azimuth`) | **50 of 122** tagger matches to one-way segments are on the opposite carriageway from the event's stated direction (an "I-80 WB" event tagged to the EB segment), across 11 of 24 directional events. |

The last row is the most useful finding for this project, and it does not need tripletrail to
fix. On divided interstates the two directions are separate one-way Overture segments 20-40 m
apart, and the tagger's nearest-segment and 25 m buffer rules do not look at direction. The
closure detour above only works because the constraint removes the right carriageway; with
the current tags it also closes the open direction.

## Fit and recommendation

**Good fit for**

1. **Routing over GERS.** pgRouting semantics, one-way handling, turn restrictions
   (`pgr_trsp`), constraints over edge attributes (`?c_*` columns), contraction hierarchies for
   repeated queries, and `withPoints` to start or end a route at an event's `at` on a segment.
   Results are GERS linear references with no ID translation.
2. **Event-aware operations queries** in one place: detours around closures, upstream reach for
   alerting, single points of failure on a corridor.
3. **Linear referencing and conflation primitives** (`intrinsicAt`, `locate`, `conflate`) that
   map directly onto Overture's `at`/`between` model.

**Less of a fit**

- It is an RDF store: everything goes through a lift to triples, and SPARQL is a new language
  for the team. For a static GitHub Pages demo it would need a hosted server (it is a
  Fuseki-compatible HTTP service), which this repo does not have today.
- Very new (v0.1.0, no release yet, single vendor). Fine for exploration, not yet something to
  build the state playbook on.
- The DuckDB tagger already does the matching well for points; tripletrail does not replace it.

**Next steps, in order of value**

1. **Fix direction in the tagger** (no tripletrail needed): when an event names EB/WB/NB/SB,
   or a line event has a bearing, only accept one-way segments whose heading agrees within 90°.
   `direction_check.rq` is the test.
2. **Emit `at` / `between` in the tagger's `location_references`**, so each match is a full
   GERS linear reference. DuckDB spatial has `ST_LineLocatePoint`; `linear_ref.rq` shows the output.
3. If routing is wanted in the demo or the USDOT pitch, **run tripletrail as a small service**
   over one corridor (I-80 IA-NE) and expose two endpoints: route and closure-aware detour,
   returning GERS references. The queries here are that service's core.
4. Try `pgr_trsp` with Overture `prohibited_transitions` (turn restrictions), which this
   experiment does not load yet.
