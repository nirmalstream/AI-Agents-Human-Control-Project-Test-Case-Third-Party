#!/usr/bin/env bash
# Run the test case. Works in Terminal on macOS/Linux and in Git Bash on Windows.
#
#   ./run.sh simulated 01            one baseline run with the simulated user  -> runs/run-01/
#   ./run.sh human 06                user testing: a person types the replies  -> runs/run-06/
#   ./run.sh human 06 --tts          ... and the agent's messages are read aloud on this computer
#   ./run.sh simulated 01 --layer on run the proposed agent (not built yet)
#
#   for i in 01 02 03 04 05; do ./run.sh simulated $i; done      the 5 baseline runs
#
#   ./run.sh build | selftest | persona | test | summary
#
# Each run: stop everything -> start the sites fresh -> run the agent -> score -> stop everything.
# A run that failed because the model provider was unavailable is moved to runs/invalid/ and redone
# the next time you run the same number; a valid run is never overwritten.
set -euo pipefail
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1   # Git Bash on Windows: do not rewrite /output-style paths

compose() { docker compose "$@"; }
in_agent() { compose --profile agent run --rm --no-deps -T agent "$@"; }

wait_sites() {
  for port in 5000 5001 5002; do
    for _ in $(seq 40); do curl -fs "http://localhost:$port/__health" >/dev/null 2>&1 && continue 2; sleep 1; done
    echo "A site on port $port did not start. Is Docker Desktop running (and not paused)?" >&2; exit 1
  done
}

start_sites() { compose --profile agent down >/dev/null 2>&1 || true; compose up -d flyscout northbeam tripsaverly >/dev/null; wait_sites; }
stop_all() { compose --profile agent down >/dev/null 2>&1 || true; }

# Optional text-to-speech on the host (Docker containers cannot play sound on your speakers).
speaker_pid=""
start_tts() {
  local dir="$1/tts"; mkdir -p "$dir"
  (
    spoken=0
    while true; do
      for f in "$dir"/*.txt; do
        [ -e "$f" ] || continue
        n=$(basename "$f" .txt); n=$((10#$n))
        [ "$n" -le "$spoken" ] && continue
        if command -v say >/dev/null; then say -f "$f"                                   # macOS
        elif command -v powershell.exe >/dev/null; then                                  # Windows
          powershell.exe -NoProfile -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak([IO.File]::ReadAllText('$(cygpath -w "$f")'))" >/dev/null 2>&1
        elif command -v espeak-ng >/dev/null; then espeak-ng -f "$f"                    # Linux
        fi
        spoken=$n
      done
      sleep 0.5
    done
  ) &
  speaker_pid=$!
}
stop_tts() { [ -n "$speaker_pid" ] && kill "$speaker_pid" 2>/dev/null || true; }

valid_run() { grep -q '"valid_run": 1' "$1/reward.json" 2>/dev/null; }

case "${1:-}" in
  build)    compose --profile agent build; exit 0 ;;
  test)     in_agent python test_make_outputs.py; exit 0 ;;
  persona)  in_agent python run_case.py persona; exit 0 ;;
  summary)  here="$(pwd -W 2>/dev/null || pwd)"   # pwd -W gives C:/... in Git Bash
            compose --profile agent run --rm --no-deps -T -v "$here/runs:/runs" agent python make_outputs.py --summary /runs; exit 0 ;;
  selftest)
    export RUN_DIR=./runs/scratch; mkdir -p runs/scratch/site_logs
    start_sites; trap stop_all EXIT
    compose --profile agent run --rm -T agent python run_case.py selftest; exit $? ;;
  simulated|human|scripted) ;;
  *) sed -n '2,17p' "$0"; exit 1 ;;
esac

MODE="$1"; ID="${2:?give a run number, e.g. ./run.sh simulated 01}"; shift 2
LAYER=off; TTS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --layer) LAYER="${2:?--layer on|off}"; shift 2 ;;
    --tts) TTS=1; shift ;;
    *) echo "unknown option $1" >&2; exit 1 ;;
  esac
done
if [ "$LAYER" = on ]; then echo "--layer on: the proposed layer is not built yet. Run without it for the baseline." >&2; exit 1; fi

DIR="runs/run-$ID"
if [ -e "$DIR" ]; then
  if valid_run "$DIR"; then echo "$DIR already has a valid run; skipping (move it away to redo it)."; exit 0; fi
  mkdir -p runs/invalid; dest="runs/invalid/run-$ID-$(date +%Y%m%d-%H%M%S)"; mv "$DIR" "$dest"
  echo "$DIR was not a valid run (moved to $dest); running it again."
fi
mkdir -p "$DIR/site_logs"
export RUN_DIR="./$DIR" MODE LAYER

echo "== run-$ID: reset"
start_sites
trap 'stop_tts; stop_all' EXIT

echo "== run-$ID: agent running (mode $MODE, layer $LAYER)"
if [ "$MODE" = human ]; then
  [ "$TTS" = 1 ] && start_tts "$DIR"
  # Git Bash's default window (mintty) needs winpty for an interactive container.
  if [[ "$(uname -s)" == MINGW* ]] && command -v winpty >/dev/null && [ -z "${WT_SESSION:-}" ]; then
    winpty docker compose --profile agent run --rm agent python run_case.py
  else
    compose --profile agent run --rm agent python run_case.py
  fi
  stop_tts
else
  compose --profile agent run --rm -T agent python run_case.py 2>&1 | grep -E '\[agent -> user\]|\[user -> agent\]|run finished' || true
fi

echo "== run-$ID: scoring"
compose --profile agent run --rm --no-deps -T agent python make_outputs.py /output "run-$ID"
valid_run "$DIR" || echo "WARNING: run-$ID is not valid (model provider unavailable?). Run the same command again later to redo it."
