#!/usr/bin/env python3
"""gers-tagger: attach Overture GERS location references to a road-event feed.

Feed in (WZDx / ArcGIS / GeoJSON) -> same feed out, each event carrying
`location_references`: [{type: "gers", gers_id, overture_release, match: {...}}]
plus a match report with the numbers that matter (match rate, median snap).

Requires: pip install duckdb duckdb-extension-httpfs duckdb-extension-spatial

Examples:
  # ArcGIS feature layer (paginates automatically)
  python3 gers_tagger.py \
    --events "https://services.arcgis.com/ORG/arcgis/rest/services/LAYER/FeatureServer/0" \
    --route-field Route --out tagged/

  # WZDx v4.x feed or any GeoJSON FeatureCollection (URL or local file)
  python3 gers_tagger.py --events https://state.gov/wzdx/feed.geojson --out tagged/

  # Offline / repeat runs against a cached segment extract
  python3 gers_tagger.py --events feed.geojson --segments cache/segments.parquet --out tagged/
"""
import argparse, json, os, re, ssl, sys, urllib.parse, urllib.request

RELEASE = "2026-11-18.0"  # override with --release; check overturemaps.org for latest
S3 = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
UTM = "EPSG:26915"  # ponytail: one CONUS-middle zone; metric error < ~0.5% at the margins,
                    # fine for 250 m snap tests. Per-zone transform if you need survey grade.

def opener():
    ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
    handlers = [urllib.request.HTTPSHandler(context=ctx)]
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        handlers.insert(0, urllib.request.ProxyHandler({"https": proxy}))
    return urllib.request.build_opener(*handlers)

def fetch_events(src, op):
    """Return a list of GeoJSON features from a file, FeatureCollection URL, or ArcGIS layer."""
    if os.path.exists(src):
        d = json.load(open(src))
    elif "/FeatureServer/" in src or "/MapServer/" in src:
        base = src.split("/query")[0].rstrip("/")
        feats, offset = [], 0
        while True:
            q = urllib.parse.urlencode({"f": "geojson", "where": "1=1", "outFields": "*",
                "returnGeometry": "true", "outSR": "4326",
                "resultOffset": offset, "resultRecordCount": 1000})
            d = json.load(op.open(f"{base}/query?{q}", timeout=60))
            fs = d.get("features", [])
            feats += fs
            if len(fs) < 1000:
                return feats
            offset += 1000
    else:
        d = json.load(op.open(src, timeout=120))
    return d.get("features", d if isinstance(d, list) else [])

def route_ref(props, field):
    txt = str(props.get(field) or "") if field else " ".join(str(v) for v in props.values() if isinstance(v, str))
    m = re.search(r"\bI-?\s?(\d{1,3})\b", txt)
    return int(m.group(1)) if m else None

def list_release_files(op, release):
    prefix = f"release/{release}/theme%3Dtransportation/type%3Dsegment/"
    keys, token = [], None
    while True:
        u = f"{S3}/?list-type=2&prefix={prefix}"
        if token:
            u += "&continuation-token=" + urllib.parse.quote(token)
        xml = op.open(u, timeout=60).read().decode()
        keys += re.findall(r"<Key>([^<]+parquet)</Key>", xml)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", xml)
        if not m:
            return [f"{S3}/{k.replace('=', '%3D')}" for k in keys]
        token = m.group(1)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", required=True, help="Feed URL (WZDx/GeoJSON/ArcGIS layer) or local file")
    ap.add_argument("--out", default="tagged", help="Output directory")
    ap.add_argument("--release", default=RELEASE, help="Overture release to reference")
    ap.add_argument("--route-field", default=None, help="Property holding the route name (else parsed from all text)")
    ap.add_argument("--segments", default=None, help="Local parquet of segments (id,name,class,route_ref,geom) to skip the Overture fetch")
    ap.add_argument("--classes", default="motorway", help="Overture road classes, comma-separated (motorway,trunk,primary)")
    ap.add_argument("--max-snap", type=float, default=250, help="Max point-to-segment distance, meters")
    ap.add_argument("--line-buffer", type=float, default=25, help="Buffer for line events, meters")
    ap.add_argument("--min-overlap", type=float, default=80, help="Min line overlap to count a segment, meters")
    ap.add_argument("--margin", type=float, default=0.05, help="Degrees added around the events' extent for the segment fetch")
    a = ap.parse_args()

    import duckdb
    op = opener()
    os.makedirs(a.out, exist_ok=True)
    con = duckdb.connect()
    for ext in ("httpfs", "spatial"):
        try:
            con.execute(f"LOAD {ext}")
        except Exception:
            try:  # duckdb-extension-* pip packages ship the binary; load it by path
                import importlib
                pkg = importlib.import_module(f"duckdb_extension_{ext}")
                base = os.path.dirname(pkg.__file__)
                hits = [os.path.join(r, f) for r, _, fs in os.walk(base)
                        for f in fs if f == f"{ext}.duckdb_extension"]
                con.execute(f"LOAD '{hits[0]}'")
            except Exception:
                con.execute(f"INSTALL {ext}; LOAD {ext}")
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        con.execute(f"SET http_proxy='{proxy}'")
        if os.environ.get("SSL_CERT_FILE"):
            con.execute(f"SET ca_cert_file='{os.environ['SSL_CERT_FILE']}'")
    con.execute("SET geometry_always_xy = true")

    feats = fetch_events(a.events, op)
    rows = []
    for i, f in enumerate(feats):
        g = f.get("geometry")
        if not g or not g.get("coordinates"):
            continue
        rows.append({"idx": i, "iref": route_ref(f.get("properties", {}), a.route_field),
                     "geom": json.dumps(g)})
    if not rows:
        sys.exit("no events with geometry found")
    json.dump(rows, open(f"{a.out}/_ev.json", "w"))
    con.execute(f"CREATE TABLE ev AS SELECT * FROM read_json('{a.out}/_ev.json', format='array')")
    con.execute("ALTER TABLE ev ADD COLUMN geometry GEOMETRY")
    con.execute("UPDATE ev SET geometry = ST_GeomFromGeoJSON(geom)")
    ext_q = con.execute("SELECT min(ST_XMin(geometry)), max(ST_XMax(geometry)), min(ST_YMin(geometry)), max(ST_YMax(geometry)) FROM ev").fetchone()
    x0, x1, y0, y1 = ext_q[0]-a.margin, ext_q[1]+a.margin, ext_q[2]-a.margin, ext_q[3]+a.margin
    print(f"{len(rows)} events | extent {x0:.2f},{y0:.2f} .. {x1:.2f},{y1:.2f}")

    classes = ",".join(f"'{c.strip()}'" for c in a.classes.split(","))
    if a.segments:
        con.execute(f"CREATE TABLE seg AS SELECT * EXCLUDE(geom), ST_GeomFromGeoJSON(geom) AS geometry FROM '{a.segments}'")
    else:
        urls = list_release_files(op, a.release)
        ulist = "[" + ",".join(f"'{u}'" for u in urls) + "]"
        print(f"fetching Overture segments from {len(urls)} parquet files (bbox pushdown; a few minutes)...")
        con.execute(f"""
            CREATE TABLE seg AS
            SELECT id, names.primary AS name, class,
              CASE WHEN routes IS NOT NULL AND len(routes)>0
                   THEN routes[1].network || ' ' || routes[1].ref END AS route_ref,
              geometry
            FROM read_parquet({ulist})
            WHERE subtype='road' AND class IN ({classes})
              AND (subclass IS NULL OR subclass NOT IN ('link'))
              AND bbox.xmin BETWEEN {x0} AND {x1} AND bbox.ymin BETWEEN {y0} AND {y1}""")
        con.execute(f"COPY (SELECT id,name,class,route_ref, ST_AsGeoJSON(geometry) AS geom FROM seg) TO '{a.out}/segments.parquet'")
    nseg = con.execute("SELECT count(*) FROM seg").fetchone()[0]
    print(f"{nseg} candidate segments")

    for t in ("ev", "seg"):
        con.execute(f"ALTER TABLE {t} ADD COLUMN gm GEOMETRY")
        con.execute(f"UPDATE {t} SET gm = ST_Transform(geometry,'EPSG:4326','{UTM}', always_xy := true)")
    pt = con.execute(f"""
        SELECT idx, gers_id, snap_m, route_agree FROM (
          SELECT e.idx, s.id AS gers_id, ST_Distance(e.gm,s.gm) AS snap_m,
            (e.iref IS NOT NULL AND s.route_ref = 'US:I ' || e.iref) AS route_agree,
            row_number() OVER (PARTITION BY e.idx ORDER BY
              CASE WHEN e.iref IS NOT NULL AND s.route_ref = 'US:I ' || e.iref THEN 0 ELSE 1 END,
              ST_Distance(e.gm,s.gm)) rk
          FROM ev e JOIN seg s ON ST_DWithin(e.gm,s.gm,{a.max_snap})
          WHERE ST_GeometryType(e.geometry)::VARCHAR='POINT') WHERE rk=1""").fetchall()
    ln = con.execute(f"""
        SELECT idx, gers_id, overlap_m, route_agree FROM (
          SELECT e.idx, s.id AS gers_id,
            ST_Length(ST_Intersection(ST_Buffer(e.gm,{a.line_buffer}),s.gm)) AS overlap_m,
            (e.iref IS NOT NULL AND s.route_ref = 'US:I ' || e.iref) AS route_agree
          FROM ev e JOIN seg s ON ST_DWithin(e.gm,s.gm,{a.line_buffer+5})
          WHERE ST_GeometryType(e.geometry)::VARCHAR LIKE '%LINESTRING')
        WHERE overlap_m > {a.min_overlap}""").fetchall()

    refs = {}
    for idx, gid, snap, ra in pt:
        refs.setdefault(idx, []).append({"type": "gers", "gers_id": gid, "overture_release": a.release,
            "match": {"method": "nearest-segment", "snap_m": round(snap, 1), "route_agree": bool(ra)}})
    for idx, gid, ov, ra in ln:
        refs.setdefault(idx, []).append({"type": "gers", "gers_id": gid, "overture_release": a.release,
            "match": {"method": "buffer-overlap", "overlap_m": round(ov), "route_agree": bool(ra)}})
    for i, f in enumerate(feats):
        if i in refs:
            f.setdefault("properties", {})["location_references"] = refs[i]
    json.dump({"type": "FeatureCollection", "features": feats},
              open(f"{a.out}/tagged.geojson", "w"), separators=(",", ":"))

    import statistics
    snaps = sorted(r[2] for r in pt)
    report = {"events_in": len(feats), "events_with_geometry": len(rows),
              "events_matched": len(refs), "segment_candidates": nseg,
              "point_matches": len(pt), "line_segment_refs": len(ln),
              "median_snap_m": round(statistics.median(snaps), 1) if snaps else None,
              "route_consistent_points": sum(1 for r in pt if r[3]),
              "overture_release": a.release}
    json.dump(report, open(f"{a.out}/report.json", "w"), indent=2)
    os.remove(f"{a.out}/_ev.json")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
