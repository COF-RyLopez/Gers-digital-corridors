import {geoAlbers, geoPath, geoArea, GeoProjection} from 'd3-geo';
import usStatesRaw from './us_states.json';
import segments from './video_segments.json';
import events from './video_events.json';
import eventsV3 from './video_events_v3.json';
import liveStates from './video_live_states.json';

// d3-geo uses spherical winding; RFC 7946 rings render inverted. Rewind oversized rings.
const rewindRing = (ring: number[][]) =>
  geoArea({type: 'Polygon', coordinates: [ring]} as never) > Math.PI ? [...ring].reverse() : ring;
const rewind = (g: any): any => {
  if (g.type === 'Polygon') return {...g, coordinates: g.coordinates.map(rewindRing)};
  if (g.type === 'MultiPolygon') return {...g, coordinates: g.coordinates.map((p: number[][][]) => p.map(rewindRing))};
  return g;
};
const usStates = {
  type: 'FeatureCollection',
  features: (usStatesRaw as any).features.map((f: any) => ({...f, geometry: rewind(f.geometry)})),
};

export const C = {
  bg: '#14181D', panel: '#1C2228', ink: '#E8EDF2', muted: '#93A0AD', line: '#2D353E',
  blue: '#5AA4E0', orange: '#F08A2E', road: '#49555F',
  IA: '#A78CE0', NE: '#4FB06C', MN: '#4DB3D6', MO: '#E0707A',
  GA: '#D8C155', UT: '#E0876A', NM: '#A4C653', KY: '#6FB3DC',
} as const;

const W = 1920, H = 1080;

const mkProj = (extent: [[number, number], [number, number]], pad: number): GeoProjection =>
  geoAlbers().rotate([96, 0]).fitExtent(
    [[pad, pad], [W - pad, H - pad]],
    {type: 'MultiPoint', coordinates: [extent[0], extent[1], [extent[0][0], extent[1][1]], [extent[1][0], extent[0][1]]]} as never,
  );

// National view: CONUS
export const projUS = geoAlbers().rotate([96, 0]).fitExtent([[80, 120], [W - 80, H - 60]], usStates as never);
// Corridor view: the 4-state window
export const projMW = mkProj([[-97.6, 36.3], [-88.9, 47.2]], 90);

const pathUS = geoPath(projUS);
const pathMW = geoPath(projMW);

export const statePathsUS: {name: string; d: string}[] = (usStates as any).features
  .map((f: any) => ({name: f.properties.name, d: pathUS(f) ?? ''}))
  .filter((s: any) => s.d);

const MW_NAMES = new Set(['Iowa', 'Nebraska', 'Minnesota', 'Missouri']);
export const statePathsMW: {name: string; d: string; active: boolean}[] = (usStates as any).features
  .map((f: any) => ({name: f.properties.name, d: pathMW(f) ?? '', active: MW_NAMES.has(f.properties.name)}))
  .filter((s: any) => s.d);

// Interstates grouped by route -> one concatenated path string each (fast to draw)
const groups = new Map<string, string[]>();
for (const s of segments as any[]) {
  const d = pathMW(s.g as never);
  if (d) {
    const arr = groups.get(s.r) ?? [];
    arr.push(d);
    groups.set(s.r, arr);
  }
}
export const routePaths: {route: string; d: string}[] = [...groups.entries()].map(([route, ds]) => ({
  route, d: ds.join(' '),
}));

export const eventDots: {s: keyof typeof C; x: number; y: number}[] = (events as any[])
  .map((e) => {
    const p = projMW(e.c as [number, number]);
    return p ? {s: e.s, x: p[0], y: p[1]} : null;
  })
  .filter(Boolean) as never;

// Freight route LA -> Omaha (I-15 / I-70 / I-76 / I-80 waypoints), projected on the US view
const FREIGHT: [number, number][] = [
  [-118.22, 33.75], [-117.3, 34.1], [-116.2, 34.85], [-115.15, 36.1], [-114.5, 37.0],
  [-113.6, 37.7], [-112.1, 38.6], [-110.8, 38.95], [-109.5, 39.0], [-108.55, 39.1],
  [-107.3, 39.4], [-106.1, 39.65], [-104.99, 39.74], [-103.8, 40.2], [-102.3, 40.9],
  [-101.0, 41.1], [-99.0, 40.95], [-97.4, 40.9], [-96.0, 41.25],
];
export const freightPts = FREIGHT.map((c) => projUS(c)!) as [number, number][];
const cum: number[] = [0];
for (let i = 1; i < freightPts.length; i++) {
  const [x0, y0] = freightPts[i - 1], [x1, y1] = freightPts[i];
  cum.push(cum[i - 1] + Math.hypot(x1 - x0, y1 - y0));
}
export const freightLen = cum[cum.length - 1];
export const freightD = 'M' + freightPts.map((p) => p.join(',')).join('L');
export const freightAt = (t: number): [number, number] => {
  const target = Math.max(0, Math.min(1, t)) * freightLen;
  let i = 1;
  while (i < cum.length - 1 && cum[i] < target) i++;
  const f = (target - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
  const [x0, y0] = freightPts[i - 1], [x1, y1] = freightPts[i];
  return [x0 + (x1 - x0) * f, y0 + (y1 - y0) * f];
};

// --- v3: national live layer ---
const pathUSd = geoPath(projUS);
export const liveStatePaths: {state: string; d: string}[] = (liveStates as any[])
  .map((s) => ({state: s.state, d: pathUSd(s.g) ?? ''}))
  .filter((s) => s.d);
export const liveEventDots: {s: keyof typeof C; x: number; y: number}[] = (eventsV3 as any[])
  .map((e) => { const p = projUS(e.c as [number, number]); return p ? {s: e.s, x: p[0], y: p[1]} : null; })
  .filter(Boolean) as never;
