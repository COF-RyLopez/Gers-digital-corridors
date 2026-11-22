import React from 'react';
import {AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {loadFont as loadOverpass} from '@remotion/google-fonts/Overpass';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadMono} from '@remotion/google-fonts/OverpassMono';
import {C, statePathsUS, statePathsMW, routePaths, eventDots, freightD, freightAt} from './geo';

const {fontFamily: OV} = loadOverpass();
const {fontFamily: IN} = loadInter();
const {fontFamily: MONO} = loadMono();

const ease = Easing.bezier(0.2, 0.7, 0.3, 1);

const Fade: React.FC<{from: number; dur?: number; children: React.ReactNode; rise?: number; style?: React.CSSProperties}> = ({from, dur = 18, children, rise = 26, style}) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [from, from + dur], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  return <div style={{opacity: t, transform: `translateY(${(1 - t) * rise}px)`, ...style}}>{children}</div>;
};

const Kicker: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div style={{fontFamily: OV, fontWeight: 600, fontSize: 26, letterSpacing: 4, color: C.blue}}>{children}</div>
);

// ---- Scene 1 · Title (0–240) ----
const Title: React.FC = () => {
  const f = useCurrentFrame();
  const segT = interpolate(f, [55, 95], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const dots = [0, 1, 2].map((i) => interpolate(f, [110 + i * 16, 126 + i * 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  return (
    <AbsoluteFill style={{background: C.bg, padding: 140, justifyContent: 'space-between'}}>
      <div style={{display: 'flex', flexDirection: 'column', gap: 38}}>
        <Fade from={0}><Kicker>USDOT DIGITAL CORRIDORS · A WORKING DEMONSTRATION</Kicker></Fade>
        <Fade from={10}><div style={{fontFamily: OV, fontWeight: 800, fontSize: 118, lineHeight: 1.04, color: C.ink}}>One road segment.<br />One ID. Every dataset.</div></Fade>
        <Fade from={26}><div style={{fontFamily: IN, fontSize: 36, color: C.muted, width: 1350}}>Four state DOTs’ live feeds, one open segment reference — and what that unlocks for freight, safety, and every user of the interstates.</div></Fade>
      </div>
      <div style={{position: 'relative', height: 160}}>
        <svg width={1640} height={60} style={{position: 'absolute', top: 70}}>
          <line x1={0} y1={30} x2={1640} y2={30} stroke={C.road} strokeWidth={6} />
          <line x1={540} y1={30} x2={540 + 560 * segT} y2={30} stroke={C.orange} strokeWidth={10} strokeLinecap="round" />
          {dots.map((o, i) => (
            <circle key={i} cx={620 + i * 190} cy={30} r={13} fill={[C.IA, C.NE, C.blue][i]} opacity={o} />
          ))}
        </svg>
        <div style={{display: 'flex', gap: 22, position: 'absolute', top: 0}}>
          {['state 511 feed', 'fleet observation', 'federal attributes'].map((t, i) => (
            <Fade key={t} from={115 + i * 16} rise={10}>
              <div style={{fontFamily: MONO, fontSize: 25, color: C.ink, background: '#242C34', border: `2px solid ${C.line}`, borderRadius: 10, padding: '10px 18px'}}>{t}</div>
            </Fade>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene 2 · National fragmentation (240–810) ----
const DIALECTS = [
  {t: 0.06, label: 'CA · postmile 34.21', dx: -60, dy: 44},
  {t: 0.22, label: 'NV · I-15 NB milepost 48', dx: -30, dy: -100},
  {t: 0.38, label: 'UT · ref 0070 405+00', dx: -80, dy: 52},
  {t: 0.56, label: 'CO · route 070A mp 261.4', dx: 20, dy: -104},
  {t: 0.78, label: 'NE · lat 41.10, lon −101.00', dx: -10, dy: 48},
];
const National: React.FC = () => {
  const f = useCurrentFrame();
  const draw = interpolate(f, [60, 420], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad)});
  const [cx, cy] = freightAt(draw);
  const mapIn = interpolate(f, [0, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <svg width={1920} height={1080} style={{opacity: mapIn}}>
        {statePathsUS.map((s) => (
          <path key={s.name} d={s.d} fill={C.panel} stroke={C.line} strokeWidth={1.6} />
        ))}
        <path d={freightD} fill="none" stroke={C.orange} strokeWidth={6} strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw} opacity={0.9} />
        {draw > 0.005 && <circle cx={cx} cy={cy} r={14} fill={C.orange} stroke={C.bg} strokeWidth={4} />}
      </svg>
      {DIALECTS.map((d, i) => {
        const [x, y] = freightAt(d.t);
        return (
          <div key={d.label} style={{position: 'absolute', left: x + d.dx, top: y + d.dy}}>
            <Fade from={60 + 360 * d.t} dur={14} rise={14}>
              <div style={{fontFamily: MONO, fontSize: 24, color: C.ink, background: '#242C34', border: `2px solid ${C.line}`, borderRadius: 9, padding: '8px 14px', transform: `rotate(${(i % 2 ? 1 : -1) * 2}deg)`}}>{d.label}</div>
            </Fade>
          </div>
        );
      })}
      <div style={{position: 'absolute', left: 140, top: 92}}>
        <Fade from={8}><Kicker>A CONTAINER LEAVES THE PORT OF LONG BEACH</Kicker></Fade>
        <Fade from={20}><div style={{fontFamily: OV, fontWeight: 800, fontSize: 64, color: C.ink, width: 900, lineHeight: 1.1}}>Every border, a new data dialect</div></Fade>
      </div>
      <div style={{position: 'absolute', left: 140, bottom: 90}}>
        <Fade from={440}><div style={{fontFamily: IN, fontSize: 34, color: C.muted, width: 1100}}>Closures, work zones, and restrictions live in incompatible systems — <span style={{color: C.ink, fontWeight: 600}}>no dispatcher can plan 2,000 miles against twelve dialects.</span></div></Fade>
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene 3 · The join (810–1470) ----
const Join: React.FC = () => {
  const f = useCurrentFrame();
  const mapIn = interpolate(f, [0, 25], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const draw = interpolate(f, [20, 180], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad)});
  const wave = interpolate(f, [330, 480], [0, 1920], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad)});
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <svg width={1920} height={1080} style={{opacity: mapIn}}>
        {statePathsMW.map((s) => (
          <path key={s.name} d={s.d} fill={s.active ? '#1E2630' : C.panel} stroke={C.line} strokeWidth={1.6} strokeDasharray="6 6" />
        ))}
        {routePaths.map((r, i) => (
          <path key={r.route} d={r.d} fill="none" stroke={C.road} strokeWidth={3.2} pathLength={1} strokeDasharray={1}
            strokeDashoffset={Math.max(0, 1 - Math.max(0, draw * 1.6 - i * 0.05))} strokeLinecap="round" />
        ))}
        {eventDots.map((e, i) => {
          const t = interpolate(f, [170 + (i % 40) * 3, 184 + (i % 40) * 3], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const matched = e.x < wave;
          return (
            <g key={i} opacity={t}>
              {matched && <circle cx={e.x} cy={e.y} r={11} fill="none" stroke={C.orange} strokeWidth={2.5} opacity={0.85} />}
              <circle cx={e.x} cy={e.y} r={5.5} fill={C[e.s] as string} stroke={C.bg} strokeWidth={1.5} />
            </g>
          );
        })}
      </svg>
      <div style={{position: 'absolute', left: 140, top: 92}}>
        <Fade from={6}><Kicker>IOWA · NEBRASKA · MINNESOTA · MISSOURI — LIVE 511 FEEDS</Kicker></Fade>
        <Fade from={18}><div style={{fontFamily: OV, fontWeight: 800, fontSize: 64, color: C.ink, lineHeight: 1.1}}>Conflate once. Join forever.</div></Fade>
      </div>
      <div style={{position: 'absolute', right: 140, top: 110}}>
        <Fade from={320} rise={14}>
          <div style={{fontFamily: MONO, fontSize: 27, color: C.orange, background: '#242C34', border: `2px solid ${C.orange}`, borderRadius: 10, padding: '12px 20px'}}>gers_id + overture_release</div>
        </Fade>
      </div>
      <div style={{position: 'absolute', left: 140, bottom: 90}}>
        <Fade from={480}><div style={{fontFamily: IN, fontSize: 34, color: C.muted, width: 1250}}>306 real events, four schemas, one keyed network — <span style={{color: C.ink, fontWeight: 600}}>each state keeps its own data, its own LRS, its own authority.</span></div></Fade>
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene 4 · Numbers (1470–1890) ----
const Stat: React.FC<{value: string; label: string; from: number; accent?: boolean}> = ({value, label, from, accent}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f - from, fps, config: {damping: 14, mass: 0.7}});
  return (
    <div style={{transform: `scale(${0.9 + 0.1 * s})`, opacity: Math.min(1, s * 1.4), display: 'flex', flexDirection: 'column', gap: 10}}>
      <div style={{fontFamily: OV, fontWeight: 800, fontSize: 150, lineHeight: 1, color: accent ? C.orange : C.ink}}>{value}</div>
      <div style={{fontFamily: IN, fontSize: 29, color: C.muted, width: 360}}>{label}</div>
    </div>
  );
};
const Numbers: React.FC = () => (
  <AbsoluteFill style={{background: C.bg, padding: 140, justifyContent: 'center', gap: 70}}>
    <Fade from={0}><Kicker>EVERY NUMBER AUDITABLE ON THE PUBLIC DEMO</Kicker></Fade>
    <div style={{display: 'flex', gap: 90}}>
      <Stat value="306" label="live 511 events, four states" from={10} />
      <Stat value="99%" label="interstate events auto-matched" from={22} accent />
      <Stat value="3.4 m" label="median snap distance" from={34} accent />
      <Stat value="1 day" label="for a state to adopt, with the open playbook" from={46} />
    </div>
    <Fade from={70}><div style={{fontFamily: IN, fontSize: 34, color: C.muted, width: 1500}}>Built on the states’ own public feeds and the open Overture reference — no agreements, no API keys, no procurement. <span style={{color: C.ink, fontWeight: 600}}>The barrier was never technical.</span></div></Fade>
  </AbsoluteFill>
);

// ---- Scene 5 · Close (1890–2190) ----
const Close: React.FC = () => (
  <AbsoluteFill style={{background: C.bg, padding: 140, justifyContent: 'center', gap: 52}}>
    <Fade from={0}><div style={{fontFamily: OV, fontWeight: 800, fontSize: 84, lineHeight: 1.08, color: C.ink, width: 1560}}>The feeds exist. The reference exists. The conflation is solved.</div></Fade>
    <Fade from={28}><div style={{fontFamily: IN, fontSize: 40, color: C.muted}}>What remains is adoption — about a day per state.</div></Fade>
    <Fade from={48}>
      <div style={{display: 'flex', gap: 44, alignItems: 'center'}}>
        <div style={{fontFamily: MONO, fontSize: 30, color: C.blue}}>cof-rylopez.github.io/Gers-digital-corridors</div>
        <div style={{fontFamily: MONO, fontSize: 26, color: C.muted}}>demo · playbook · open-source tagger</div>
      </div>
    </Fade>
  </AbsoluteFill>
);

export const MyComposition: React.FC = () => {
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <Sequence durationInFrames={240}><Title /></Sequence>
      <Sequence from={240} durationInFrames={570}><National /></Sequence>
      <Sequence from={810} durationInFrames={660}><Join /></Sequence>
      <Sequence from={1470} durationInFrames={420}><Numbers /></Sequence>
      <Sequence from={1890} durationInFrames={300}><Close /></Sequence>
    </AbsoluteFill>
  );
};
