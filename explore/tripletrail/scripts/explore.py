#!/usr/bin/env python3
"""Run the exploration queries against a running tripletrail server and print a summary.

  tripletrail serve --load data/graph.nt --load data/events.nt     # in another shell
  python3 scripts/explore.py                                       # default trip: I-80 east of Altoona -> west Des Moines, through the I-80 WB closure

Writes data/route.geojson and data/detour.geojson so the two paths can be dropped on a map.
"""
import argparse, csv, io, json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
Q = os.path.join(HERE, "..", "queries")
DATA = os.path.join(HERE, "..", "data")


def sparql(endpoint, name, **subs):
    q = open(os.path.join(Q, name)).read()
    for k, v in subs.items():
        q = q.replace("{{" + k + "}}", str(v))
    req = urllib.request.Request(endpoint, data=urllib.parse.urlencode({"query": q}).encode(),
                                 headers={"Accept": "text/csv"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost, no proxy
    t = time.time()
    body = opener.open(req, timeout=600).read().decode()
    rows = list(csv.DictReader(io.StringIO(body)))
    return rows, time.time() - t


def wkt_coords(w):
    inner = w[w.index("(") + 1:w.rindex(")")]
    return [[float(x) for x in p.split()] for p in inner.split(",")]


def to_geojson(rows, path):
    feats = [{"type": "Feature", "properties": {k: r[k] for k in r if k != "wkt"},
              "geometry": {"type": "LineString", "coordinates": wkt_coords(r["wkt"])}} for r in rows]
    json.dump({"type": "FeatureCollection", "features": feats}, open(path, "w"))


def summary(rows):
    if not rows:
        return "no path"
    secs = float(rows[-1]["agg_secs"]) + float(rows[-1]["secs"])
    segs = []
    for r in rows:
        if not segs or segs[-1] != r["seg"]:
            segs.append(r["seg"])
    names = []
    for r in rows:
        n = r.get("name") or r["class"]
        if not names or names[-1] != n:
            names.append(n)
    return f"{secs/60:.1f} min, {len(rows)} edges on {len(segs)} GERS segments via " + " > ".join(names[:12])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://127.0.0.1:7878/ds/query")
    ap.add_argument("--start", default="POINT(-93.39489 41.680585)", help="WKT point (I-80 east of Altoona)")
    ap.add_argument("--end", default="POINT(-93.830 41.6000)", help="WKT point (west Des Moines, I-80/I-35)")
    ap.add_argument("--reach-secs", type=int, default=600)
    a = ap.parse_args()
    ep = a.endpoint

    (s,), _ = sparql(ep, "nearest_connector.rq", POINT=a.start)
    (e,), _ = sparql(ep, "nearest_connector.rq", POINT=a.end)
    print(f"start connector {s['connector']} ({float(s['m']):.0f} m from point)")
    print(f"end   connector {e['connector']} ({float(e['m']):.0f} m from point)")

    route, t1 = sparql(ep, "route.rq", START=s["connector"], END=e["connector"])
    print(f"\nroute  [{t1*1000:.0f} ms]: {summary(route)}")
    to_geojson(route, os.path.join(DATA, "route.geojson"))
    detour, t2 = sparql(ep, "detour.rq", START=s["connector"], END=e["connector"])
    print(f"detour [{t2*1000:.0f} ms]: {summary(detour)}")
    to_geojson(detour, os.path.join(DATA, "detour.geojson"))
    a_ids = {r["seg"] for r in route}
    b_ids = {r["seg"] for r in detour}
    print(f"  segments only on the original route: {len(a_ids - b_ids)}, only on the detour: {len(b_ids - a_ids)}")
    print("  first GERS linear references of the route:")
    for r in route[:3]:
        print(f"    {r['seg'].rsplit('/', 1)[-1]}  between [{float(r['from_at']):.3f}, {float(r['to_at']):.3f}]")

    reach, t3 = sparql(ep, "upstream_reach.rq", START=e["connector"], SECS=a.reach_secs)
    print(f"\nupstream reach [{t3*1000:.0f} ms]: {len(reach)} connectors can reach the end point within {a.reach_secs//60} min")

    br, t4 = sparql(ep, "bridges.rq")
    print(f"bridges [{t4*1000:.0f} ms]: {len(br)} motorway/trunk segments are single points of failure in the extract")

    lr, t5 = sparql(ep, "linear_ref.rq")
    print(f"\nlinear refs [{t5*1000:.0f} ms]: {len(lr)} point-event matches turned into segment id + at")
    for r in lr[:4]:
        print(f"    {r['event'].rsplit('/', 1)[-1]:<28} at={float(r['at']):.3f}  snap={float(r['snap_m']):.1f} m")

    cf, t6 = sparql(ep, "conflate_lines.rq")
    ev = {}
    for r in cf:
        ev.setdefault(r["event"], []).append(r)
    agree = sum(1 for r in cf if r["tagged"] == "true")
    tagged_pairs, _ = sparql(ep, "tagged_line_pairs.rq")
    n_tagged = int(tagged_pairs[0]["n"])
    print(f"conflate [{t6*1000:.0f} ms]: {len(cf)} segments at least half covered by {len(ev)} line events; "
          f"{agree} shared with the DuckDB tagger's {n_tagged}, {len(cf) - agree} new, {n_tagged - agree} tagger-only")
    dc, t7 = sparql(ep, "direction_check.rq")
    wrong = [r for r in dc if r["wrong_side"] == "true"]
    print(f"direction check [{t7*1000:.0f} ms]: {len(wrong)} of {len(dc)} matches to one-way segments sit on the "
          f"opposite carriageway from the event's stated direction, across "
          f"{len({r['event'] for r in wrong})} of {len({r['event'] for r in dc})} directional events")
    json.dump({"wrong_side": len(wrong), "directional_matches": len(dc), "route": summary(route), "detour": summary(detour), "reach": len(reach), "bridges": len(br),
               "linear_refs": len(lr), "conflate_pairs": len(cf), "conflate_agree": agree, "tagger_line_pairs": n_tagged,
               "conflate_events": len(ev)}, open(os.path.join(DATA, "summary.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
