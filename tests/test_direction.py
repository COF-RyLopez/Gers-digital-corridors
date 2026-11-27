"""Direction check: a WB event must not match the EB carriageway. Offline, no Overture fetch."""
import importlib, importlib.util, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("gers_tagger", os.path.join(HERE, "..", "tools", "gers_tagger.py"))
tagger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tagger)


@pytest.mark.parametrize("props, want", [
    ({"route": "I-80 WB"}, 270), ({"headline": "I-35 NB: Closed"}, 0),
    ({"direction": "Eastbound"}, 90), ({"core_details": {"direction": "southbound"}}, 180),
    ({"route": "I-80"}, None), ({"headline": "I-80 EB and WB: Closed"}, None),
    ({"eid": "IADOT-24884565236WB"}, None),  # a suffix inside an id is not a direction
])
def test_heading_of(props, want):
    assert tagger.heading_of(props) == want


def con_with_spatial():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    try:
        con.execute("LOAD spatial")
    except Exception:
        pkg = importlib.import_module("duckdb_extension_spatial")
        base = os.path.dirname(pkg.__file__)
        hit = [os.path.join(r, f) for r, _, fs in os.walk(base) for f in fs if f == "spatial.duckdb_extension"][0]
        con.execute(f"LOAD '{hit}'")
    return con


def test_direction_ok_picks_the_right_carriageway():
    con = con_with_spatial()
    # Two parallel one-way carriageways 30 m apart (metric coords). EB runs west->east on the
    # south side, WB east->west on the north side; the event point sits nearer the EB one.
    con.execute("""CREATE TABLE seg AS SELECT * FROM (VALUES
        ('eb', 'forward', ST_GeomFromText('LINESTRING(0 0, 1000 0)')),
        ('wb', 'forward', ST_GeomFromText('LINESTRING(1000 30, 0 30)')),
        ('wb_rev', 'backward', ST_GeomFromText('LINESTRING(0 60, 1000 60)')),
        ('two_way', NULL, ST_GeomFromText('LINESTRING(0 -20, 1000 -20)'))) t(id, oneway, gm)""")
    con.execute("""CREATE TABLE ev AS SELECT * FROM (VALUES
        (1, 270.0, ST_Point(500, 5)), (2, 90.0, ST_Point(500, 5)), (3, NULL, ST_Point(500, 5))) t(idx, heading, gm)""")
    rows = con.execute(f"""SELECT e.idx, list(s.id ORDER BY s.id) FROM ev e JOIN seg s
        ON {tagger.direction_ok('e.gm')} GROUP BY 1 ORDER BY 1""").fetchall()
    assert rows == [(1, ["two_way", "wb", "wb_rev"]),          # WB: never the EB carriageway
                    (2, ["eb", "two_way"]),                    # EB: neither WB one
                    (3, ["eb", "two_way", "wb", "wb_rev"])]    # no direction named: no filter
