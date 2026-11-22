# GERS Digital Corridors — explainer video

`gers-digital-corridors.mp4` — **1920×1080, 30 fps, 73.0 s (2,190 frames), H.264, silent (no audio track)**.
Rendered with Remotion from the source in `remotion-src/` — every frame is regenerable,
so for Blender work you can re-render any scene at any resolution, export PNG frame
sequences, or rebuild shots from the raw GeoJSON rather than compositing over the MP4.

## Scenes and timestamps

| # | Time | Frames | Scene | Contents |
|---|------|--------|-------|----------|
| 1 | 0:00–0:08 | 0–239 | **Title** | "One road segment. One ID. Every dataset." Orange segment draws on a gray road line; three dataset dots (purple/green/blue) attach; mono chips: state 511 feed · fleet observation · federal attributes · gers_id. |
| 2 | 0:08–0:27 | 240–809 | **National fragmentation** | Dark US map (real Overture state boundaries, Albers projection). Orange freight path traces Port of Long Beach → Omaha (I-15/I-70/I-80 waypoints) with a moving dot; five mismatched "data dialect" chips pop at border crossings (CA postmile, NV milepost, UT ref, CO route/mp, NE lat/lon). Caption: "Every border, a new data dialect." |
| 3 | 0:27–0:49 | 810–1469 | **The join** | Midwest window. Real interstate geometry (11,997 Overture segments, grouped per route) draws on; 306 real 511 events pop as dots colored by state (IA purple, NE green, MN cyan, MO rose); orange match-wave sweeps west→east ringing each dot; chip "gers_id + overture_release". Caption: "Conflate once. Join forever." |
| 4 | 0:49–1:03 | 1470–1889 | **Numbers** | Spring-in stat cards: 306 · 99% · 3.4 m · 1 day. |
| 5 | 1:03–1:13 | 1890–2189 | **Close** | "The feeds exist. The reference exists. The conflation is solved." + site URL. |

## Design tokens

Background `#14181D`, panel `#1C2228`, ink `#E8EDF2`, muted `#93A0AD`,
interstate blue `#5AA4E0`, work-zone orange `#F08A2E` (hero accent),
state colors: IA `#A78CE0` · NE `#4FB06C` · MN `#4DB3D6` · MO `#E0707A`.
Fonts: Overpass (titles), Inter (body), Overpass Mono (data chips).

## Source assets in `remotion-src/`

- `Composition.tsx` — all five scenes (React/Remotion; frame timings above map 1:1)
- `geo.ts` — d3-geo Albers projections, polygon rewinding, freight-route waypoints
- `us_states.json` — 49 CONUS state boundaries (Overture divisions, simplified)
- `video_segments.json` — the real interstate segments (route + geometry)
- `video_events.json` — the 306 real events (state, point, route)
- `Root.tsx` / `index.ts` / `package.json` / `remotion.config.ts` — project glue

To re-render: `npx create-video@latest --yes --blank --no-tailwind`, drop these
files into `src/` (config + package merge at root), `npm i d3-geo @remotion/google-fonts`,
then `npx remotion render Corridor out.mp4`. PNG frames for Blender:
`npx remotion render Corridor frames --sequence --image-format=png`.

The same GeoJSON (full-fidelity versions) lives in `demo/data/` at the repo root.
