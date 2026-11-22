# GERS Digital Corridors

Strategy brief and working demo for Overture Maps Foundation's engagement with the
USDOT Digital Corridors Initiative.

- **`index.html`** — strategy brief: DCI research, AV/OEM data-sharing standards landscape,
  the proposed GERS-Referenced Observation Profile, corridor operations ladder,
  reference architecture, and pilot spec.
- **`demo/`** — interactive demo: 306 live 511 events from four state DOTs
  (Iowa, Nebraska, Minnesota, Missouri) conflated to Overture GERS IDs across the
  I-80 / I-35 / I-29 / I-70 / I-94 freight network. 99% of interstate point events
  auto-matched, median snap 3.4 m. A second tab shows the AV-fleet feedback concept
  on the Fresno SR-99 corridor (sample data).

Data sources: Iowa DOT public ArcGIS services (CARS 511 multi-state views + Missouri 511)
and Overture Maps release 2026-11-18.0 (transportation + divisions themes).
Event data is a snapshot fetched 2026-11-22.

Serve locally: `python3 -m http.server` from this directory, or enable GitHub Pages
(root of `main`).
