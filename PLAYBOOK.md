# The GERS Corridor Playbook

**How any state DOT, county, MPO, or corridor coalition can join its road-event data
to a shared national reference — in about a day, with the tools in this repository.**

The [live demo](https://cof-rylopez.github.io/Gers-digital-corridors/demo/) shows the
result at four-state scale: 306 real 511 events from Iowa, Nebraska, Minnesota, and
Missouri joined to Overture GERS segment IDs across the I-80 / I-35 / I-29 / I-70 / I-94
network — 99% of interstate point events auto-matched, median snap 3.4 meters, with
match provenance on every join. Nothing about those four states is special. This
document is the recipe for doing the same with yours.

## Why

Every road-event feed in the country today references location as raw coordinates,
a state-specific linear reference, or both. Every consumer — the neighboring state,
Google, each OEM, each freight dispatcher — re-map-matches every feed against its own
basemap. A GERS reference makes the join a key lookup instead:

- **You keep your schema.** WZDx/CWZ, your 511 vendor's format, your LRS route IDs —
  all unchanged. The reference is additive.
- **You keep your authority.** Your feed stays on your infrastructure. The reference
  dataset (Overture) is open, versioned monthly, and free.
- **Cross-jurisdiction joins come for free.** Any two GERS-tagged feeds are one
  dataset, no bilateral integration.

## Prerequisites

- A public road-event feed: WZDx/CWZ, an ArcGIS feature layer, or any GeoJSON
  FeatureCollection with event geometry. ~35 states already publish one.
- Python 3.10+ and `pip install duckdb duckdb-extension-httpfs duckdb-extension-spatial`
- Nothing else. No API keys, no accounts, no GIS server.

## Step 1 — Tag your feed (minutes)

```bash
python3 tools/gers_tagger.py \
  --events "https://your-state.gov/wzdx/feed.geojson" \
  --route-field road_name \
  --out tagged/
```

This fetches the Overture segments covering your events' extent (bbox pushdown
against Overture's public S3 — a few minutes the first run; pass `--segments` with the
cached parquet on repeat runs), matches each event (route-aware nearest-segment for
points, buffer-overlap for closure lines), and writes:

- `tagged/tagged.geojson` — your feed, unchanged, plus per-event
  `location_references` entries:

```json
{
  "type": "gers",
  "gers_id": "08f2...-....-....",
  "overture_release": "2026-11-18.0",
  "match": {"method": "nearest-segment", "snap_m": 2.8, "route_agree": true}
}
```

- `tagged/report.json` — your numbers: match rate, median snap distance,
  route-consistency count.

## Step 2 — Read the report like an engineer

Targets from the four-state pilot, on interstates:

| Metric | Target | If you miss it |
|---|---|---|
| Point match rate | ≥ 95% | Events are probably on roads outside `--classes` — add `trunk,primary`, or your extent clipped (raise `--margin`) |
| Median snap | < 10 m | Check your feed's coordinate order and datum; a systematic offset means a projection bug upstream |
| Route-consistent share | high on signed routes | Low values usually mean the route field needs `--route-field`, or events sit on ramps (expected) |

Every match carries its method and distance, so you can audit any single join.

## Step 3 — Publish

Add the `location_references` array to your production feed. It is additive and
non-breaking: WZDx already carries parallel location descriptions (coordinates,
mileposts, road names), and consumers that don't know GERS ignore the new field.
Keep your coordinates — they remain primary for non-GERS consumers.

Re-run the tagger on your feed's refresh cycle, and re-tag when a new Overture
release ships (monthly; segment ID churn runs under 1% per release — the release
is pinned in every reference, so consumers are never guessing which vocabulary
you used).

## Step 4 — Join someone else's feed

This is the payoff and it is one line of logic: two tagged feeds join on
`gers_id`. The demo's four-state map is exactly that — no conflation code in the
viewer at all. The same key also joins your asset inventory, your AADT, your
truck-route network, and (as standards land — see the
[strategy brief](https://cof-rylopez.github.io/Gers-digital-corridors/)) OEM and
AV fleet observations.

## Step 5 — Tell the next state

The national version of this is not a system anyone has to build — it is this
recipe, run ~50 times, plus a thin registry of who publishes what. If you run
this playbook on your feed, open an issue or PR on this repository with your
report.json numbers. The map gets one state better.

## Scope and honesty

- The tagger matches at **segment level**. Lane-level work zones need a lane index
  and linear offset on top of the segment reference — the proposed profile covers
  this; the tooling here does not yet.
- Carriageway disambiguation uses route + proximity; closures spanning both
  directions will reference both carriageways. Use your feed's direction field
  downstream.
- GERS stability is operational (sub-1%/month churn, registry + changelog), not
  contractual. Pin the release, handle the changelog, and you are fine — the same
  discipline any versioned dependency takes.

## License

Tools and documentation in this repository are offered under the MIT license.
Overture data is licensed per theme by Overture Maps Foundation; the event data
shown in the demo belongs to the publishing state DOTs.
