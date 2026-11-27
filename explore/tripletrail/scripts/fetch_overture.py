#!/usr/bin/env python3
"""Pull Overture segments + connectors for a bbox and write a routable edge graph as N-Triples.

Overture segments are not graph edges: one segment can run through several connectors.
This splits every road segment at its connectors (using each connector's `at`, 0..1 along
the segment) so each piece is one edge between two connector GERS IDs. Each edge keeps its
parent segment's GERS ID and the [from, to] range it covers, so a route result maps
straight back to GERS linear references.

Output (default data/):
  graph.nt         edges, segments, connectors as RDF (loaded by tripletrail)
  events.nt        511 events from demo/data/corridor_events.json inside the bbox, with
                   their existing GERS matches (used by the detour + conflation queries)

Requires: pip install duckdb duckdb-extension-httpfs duckdb-extension-spatial

  python3 scripts/fetch_overture.py --bbox -93.85,41.50,-93.35,41.72     # Des Moines + Altoona, I-80/I-35
"""
import argparse, importlib, json, math, os, re, urllib.request

RELEASE = "2026-11-18.0"
S3 = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
G = "https://gers.example/"          # placeholder namespace for GERS IDs (no official IRI scheme yet)
V = "https://gers.example/def#"      # tiny vocabulary used by the queries
RDF_TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
GEO = "http://www.opengis.net/ont/geosparql#"
SPEED = {"motorway": 105, "trunk": 90, "primary": 70, "secondary": 60, "tertiary": 50,
         "residential": 40, "unclassified": 40}  # km/h defaults when no speed limit is set


def connect():
    import duckdb
    con = duckdb.connect()
    for ext in ("httpfs", "spatial"):
        try:
            con.execute(f"LOAD {ext}")
        except Exception:
            pkg = importlib.import_module(f"duckdb_extension_{ext}")
            base = os.path.dirname(pkg.__file__)
            hit = [os.path.join(r, f) for r, _, fs in os.walk(base) for f in fs
                   if f == f"{ext}.duckdb_extension"][0]
            con.execute(f"LOAD '{hit}'")
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        con.execute(f"SET http_proxy='{proxy}'")
        ca = os.environ.get("SSL_CERT_FILE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else None)
        if ca:
            con.execute(f"SET ca_cert_file='{ca}'")
    con.execute("SET geometry_always_xy = true")
    return con


def list_files(release, typ):
    prefix = f"release/{release}/theme%3Dtransportation/type%3D{typ}/"
    keys, token = [], None
    while True:
        u = f"{S3}/?list-type=2&prefix={prefix}" + (f"&continuation-token={urllib.parse.quote(token)}" if token else "")
        xml = urllib.request.urlopen(u, timeout=60).read().decode()
        keys += re.findall(r"<Key>([^<]+parquet)</Key>", xml)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", xml)
        if not m:
            return [f"{S3}/{k.replace('=', '%3D')}" for k in keys]
        token = m.group(1)


def haversine(a, b):
    r = 6371008.8
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dla, dlo = la2 - la1, math.radians(b[0] - a[0])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def cut(coords, f0, f1):
    """Sub-line of coords between fractions f0 < f1 of its (geodesic) length."""
    seg = [haversine(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    total = sum(seg) or 1e-9
    d0, d1 = f0 * total, f1 * total
    out, acc = [], 0.0
    for i, s in enumerate(seg):
        a, b = coords[i], coords[i + 1]
        lo, hi = acc, acc + s
        def lerp(d):
            t = 0 if s == 0 else (d - lo) / s
            return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
        if hi >= d0 and lo <= d1:
            if not out:
                out.append(lerp(max(d0, lo)))
            out.append(lerp(min(d1, hi)) if hi > d1 else b)
        acc = hi
    if len(out) < 2:
        out = [lerp(d0), lerp(d1)] if seg else coords[:2]
    return out, (f1 - f0) * total


def lit(v):
    return json.dumps(str(v))


def wkt(coords):
    return "LINESTRING(" + ", ".join(f"{x:.6f} {y:.6f}" for x, y in coords) + ")"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", default="-93.85,41.50,-93.35,41.72")
    ap.add_argument("--release", default=RELEASE)
    ap.add_argument("--classes", default="motorway,trunk,primary,secondary,tertiary")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--events", default=os.path.join(os.path.dirname(__file__), "..", "..", "..", "demo", "data", "corridor_events.json"))
    a = ap.parse_args()
    x0, y0, x1, y1 = map(float, a.bbox.split(","))
    os.makedirs(a.out, exist_ok=True)
    con = connect()
    classes = ",".join(f"'{c}'" for c in a.classes.split(","))
    bb = f"bbox.xmin <= {x1} AND bbox.xmax >= {x0} AND bbox.ymin <= {y1} AND bbox.ymax >= {y0}"

    seg_cache = os.path.join(a.out, "segments.parquet")
    if not os.path.exists(seg_cache):
        urls = list_files(a.release, "segment")
        print(f"reading segments from {len(urls)} files (bbox pushdown)...")
        con.execute(f"""COPY (
            SELECT id, class, subclass, names.primary AS name,
                   connectors, speed_limits, access_restrictions,
                   ST_AsGeoJSON(geometry) AS geom
            FROM read_parquet([{','.join(repr(u) for u in urls)}])
            WHERE subtype = 'road' AND class IN ({classes}) AND {bb}
        ) TO '{seg_cache}'""")
    rows = con.execute(f"SELECT id, class, subclass, name, to_json(connectors), to_json(speed_limits), to_json(access_restrictions), geom FROM '{seg_cache}'").fetchall()
    print(f"{len(rows)} segments")

    out = []
    T = lambda s, p, o: out.append(f"{s} {p} {o} .")
    nconn, nedge = set(), 0
    for sid, cls, sub, name, conns, speeds, access, geom in rows:
        coords = json.loads(geom)["coordinates"]
        conns = sorted(json.loads(conns or "[]"), key=lambda c: c["at"])
        if len(conns) < 2:
            continue
        S = f"<{G}{sid}>"
        T(S, RDF_TYPE, f"<{V}Segment>")
        T(S, f"<{V}class>", lit(cls))
        if name:
            T(S, "<http://www.w3.org/2000/01/rdf-schema#label>", lit(name))
        if sub:
            T(S, f"<{V}subclass>", lit(sub))
        kmh = SPEED.get(cls, 40)
        for sl in json.loads(speeds or "[]") or []:
            mx = (sl or {}).get("max_speed") or {}
            if mx.get("value"):
                kmh = mx["value"] * (1.609 if mx.get("unit") == "mph" else 1)
                break
        # one-way: Overture marks heading-restricted access as access_restrictions with
        # when.heading = forward/backward and access_type = denied
        fwd, back = True, True
        for r in json.loads(access or "[]") or []:
            if (r or {}).get("access_type") == "denied" and not (r.get("when") or {}).get("mode") and not (r.get("when") or {}).get("using"):
                h = (r.get("when") or {}).get("heading")
                if h == "backward":
                    back = False
                elif h == "forward":
                    fwd = False
        for c0, c1 in zip(conns, conns[1:]):
            if c1["at"] <= c0["at"]:
                continue
            piece, metres = cut(coords, c0["at"], c1["at"])
            E = f"<{G}{sid}/{c0['at']:.6f}-{c1['at']:.6f}>"
            secs = metres / (kmh / 3.6)
            T(E, RDF_TYPE, f"<{V}Edge>")
            T(E, f"<{V}segment>", S)
            T(E, f"<{V}from>", f"<{G}{c0['connector_id']}>")
            T(E, f"<{V}to>", f"<{G}{c1['connector_id']}>")
            T(E, f"<{V}fromAt>", f'"{c0["at"]:.6f}"^^<http://www.w3.org/2001/XMLSchema#double>')
            T(E, f"<{V}toAt>", f'"{c1["at"]:.6f}"^^<http://www.w3.org/2001/XMLSchema#double>')
            T(E, f"<{V}lengthM>", f'"{metres:.1f}"^^<http://www.w3.org/2001/XMLSchema#double>')
            T(E, f"<{V}seconds>", f'"{secs:.1f}"^^<http://www.w3.org/2001/XMLSchema#double>')
            T(E, f"<{V}forward>", f'"{str(fwd).lower()}"^^<http://www.w3.org/2001/XMLSchema#boolean>')
            T(E, f"<{V}backward>", f'"{str(back).lower()}"^^<http://www.w3.org/2001/XMLSchema#boolean>')
            T(E, f"<{GEO}hasGeometry>", f"<{G}{sid}/{c0['at']:.6f}-{c1['at']:.6f}/geom>")
            T(f"<{G}{sid}/{c0['at']:.6f}-{c1['at']:.6f}/geom>", f"<{GEO}asWKT>", f'"{wkt(piece)}"^^<{GEO}wktLiteral>')
            nconn.update([c0["connector_id"], c1["connector_id"]])
            nedge += 1
        T(S, f"<{GEO}hasGeometry>", f"<{G}{sid}/geom>")
        T(f"<{G}{sid}/geom>", f"<{GEO}asWKT>", f'"{wkt(coords)}"^^<{GEO}wktLiteral>')
    for c in nconn:
        T(f"<{G}{c}>", RDF_TYPE, f"<{V}Connector>")
    open(os.path.join(a.out, "graph.nt"), "w").write("\n".join(out) + "\n")
    print(f"{nedge} edges, {len(nconn)} connectors -> graph.nt ({len(out)} triples)")

    # 511 events already matched by the demo, kept to the bbox
    ev = json.load(open(a.events))["events"]
    lines = []
    for e in ev:
        g = e.get("geometry") or {}
        cs = g.get("coordinates")
        pts = [cs] if g.get("type") == "Point" else (cs or [])
        if not pts or not all(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in pts):
            continue
        E = f"<{G}event/{re.sub(r'[^A-Za-z0-9_-]', '_', e['eid'])}>"
        lines.append(f"{E} {RDF_TYPE} <{V}Event> .")
        lines.append(f"{E} <http://www.w3.org/2000/01/rdf-schema#label> {lit(e.get('headline') or '')} .")
        lines.append(f"{E} <{V}style> {lit(e.get('style') or '')} .")
        lines.append(f"{E} <{V}route> {lit(e.get('route') or '')} .")
        for m in e.get("matches") or []:
            lines.append(f"{E} <{V}gers> <{G}{m['gers_id']}> .")
        w = (f"POINT({cs[0]} {cs[1]})" if g["type"] == "Point"
             else "LINESTRING(" + ", ".join(f"{x} {y}" for x, y in cs) + ")")
        lines.append(f"{E} <{GEO}hasGeometry> <{E[1:-1]}/geom> .")
        lines.append(f"<{E[1:-1]}/geom> <{GEO}asWKT> \"{w}\"^^<{GEO}wktLiteral> .")
    open(os.path.join(a.out, "events.nt"), "w").write("\n".join(lines) + "\n")
    print(f"{sum(1 for l in lines if '#Event>' in l)} events in bbox -> events.nt")


if __name__ == "__main__":
    import urllib.parse
    main()
