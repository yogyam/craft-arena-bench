#!/bin/sh
# Starts everything the LAN demo needs that is not already running, then opens the lobby: the arena waits for someone on the
# server to type !fight or !me in chat. Ctrl-C closes the lobby; the server and adapters stay up. Needs ANTHROPIC_API_KEY in the environment for the Haiku fighter.
cd "$(dirname "$0")/.."
PY=.venv/bin/python; CAB=.venv/bin/craft-arena-bench
up() { pgrep -f "$1" >/dev/null; }
$CAB server status | grep -q running || { echo "starting the Paper server"; $CAB server start; }
up "ollama serve" || { echo "starting Ollama"; nohup ollama serve > runs/ollama.log 2>&1 & sleep 2; }
up "adapters/ollama.py" || { echo "starting the Qwen adapter on 9010"; nohup $PY adapters/ollama.py --model qwen2.5:3b --port 9010 > runs/ep-ollama.log 2>&1 & }
# Each model fighter names the fastest rate it can keep (@hz); the lobby picks the slowest rate of the two fighters by default.
FIGHTERS="--vs house --vs random --vs circler --vs qwen=http://127.0.0.1:9010@2"
if [ -n "$ANTHROPIC_API_KEY" ] || up "adapters/claude.py"; then
  up "adapters/claude.py" || { echo "starting the Haiku adapter on 9020"; nohup $PY adapters/claude.py --port 9020 > runs/ep-claude.log 2>&1 & }
  FIGHTERS="$FIGHTERS --vs haiku=http://127.0.0.1:9020@1"   # a hosted model needs the 1 Hz budget
else
  echo "ANTHROPIC_API_KEY not set: the show runs without the Haiku fighter"
fi
up caffeinate || { nohup caffeinate -i -s > /dev/null 2>&1 & }
sleep 2
echo "Tell people: Java Minecraft 26.1.2, server address $(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}'):25565"
exec $CAB arena $FIGHTERS --tier 5 "$@"   # lobby: nothing happens until someone types !fight or !me in chat; add --auto for a self-running show
