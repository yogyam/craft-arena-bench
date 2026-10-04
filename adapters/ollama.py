"""Run a local Ollama model as an entrant. This is `openai_compatible.py` with Ollama's defaults; Ollama speaks the OpenAI API at /v1.

    ollama pull qwen2.5:3b
    python adapters/ollama.py --model qwen2.5:3b --port 9010

Pick a model that does not "think" before answering (qwen2.5, llama3.2, gemma3): at 2 Hz an answer must arrive in 400 ms.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openai_compatible import main  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    if not any(a.startswith("--base-url") for a in argv):
        argv = ["--base-url", "http://127.0.0.1:11434/v1", *argv]
    raise SystemExit(main(argv))
