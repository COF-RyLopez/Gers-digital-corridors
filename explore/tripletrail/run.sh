#!/usr/bin/env bash
# Build tripletrail (once), pull the Overture extract, serve it, run the exploration queries.
set -euo pipefail
cd "$(dirname "$0")"
TT_SRC=${TT_SRC:-$HOME/src/tripletrail}
if ! command -v tripletrail >/dev/null; then
  [ -d "$TT_SRC" ] || git clone --depth 1 https://github.com/Matdata-eu/tripletrail "$TT_SRC"
  cargo install --locked --path "$TT_SRC/crates/tripletrail-server"   # ~8 min, Rust 1.95+
fi
[ -f data/graph.nt ] || python3 scripts/fetch_overture.py
tripletrail serve --load data/graph.nt --load data/events.nt & SERVER=$!
trap 'kill $SERVER' EXIT
until curl -sf --noproxy '*' http://127.0.0.1:7878/ds/query --data-urlencode 'query=ASK{}' >/dev/null; do sleep 1; done
python3 scripts/explore.py | tee data/run.txt
echo "open http://127.0.0.1:7878/ for the tripletrail UI; Ctrl-C to stop"
wait $SERVER
