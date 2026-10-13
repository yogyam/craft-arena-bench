#!/bin/sh
# Starts everything the LAN demo needs that is not already running, then runs the exhibition. Ctrl-C stops the show;
# the server and adapters stay up for a challenge. Needs ANTHROPIC_API_KEY in the environment for the Haiku fighter.
cd "$(dirname "$0")/.."
PY=.venv/bin/python; CAB=.venv/bin/craft-arena-bench
up() { pgrep -f "$1" >/dev/null; }
$CAB server status | grep -q running || { echo "starting the Paper server"; $CAB server start; }
up "ollama serve" || { echo "starting Ollama"; nohup ollama serve > runs/ollama.log 2>&1 & sleep 2; }
up "adapters/ollama.py" || { echo "starting the Qwen adapter on 9010"; nohup $PY adapters/ollama.py --model qwen2.5:3b --port 9010 > runs/ep-ollama.log 2>&1 & }
FIGHTERS="--vs house --vs qwen=http://127.0.0.1:9010"
if [ -n "$ANTHROPIC_API_KEY" ]; then
  up "adapters/claude.py" || { echo "starting the Haiku adapter on 9020"; nohup $PY adapters/claude.py --port 9020 > runs/ep-claude.log 2>&1 & }
  FIGHTERS="$FIGHTERS --vs haiku=http://127.0.0.1:9020"
else
  echo "ANTHROPIC_API_KEY not set: the show runs without the Haiku fighter"
fi
up caffeinate || { nohup caffeinate -i -s > /dev/null 2>&1 & }
sleep 2
echo "Tell people: Java Minecraft 26.1.2, server address $(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}'):25565"
exec $CAB arena $FIGHTERS --tier 2 --mode both "$@"
