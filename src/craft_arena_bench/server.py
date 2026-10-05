"""The Paper server for the scoring job and for local development: download the pinned build, start it, stop it.

The jar is downloaded from PaperMC at run time and is never committed. Its checksum is pinned here with the build.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from . import MINECRAFT_VERSION, PAPER_BUILD, __version__
from .paths import repo_root
from .rcon import Rcon

PAPER_SHA256 = "1d70b1dab9cf4a6de615209a536f3a45a2186240253c428213ce2188ab95e5f7"  # paper-26.1.2-74.jar
FILL_API = "https://fill.papermc.io/v3/projects/paper/versions/{version}/builds"
RCON_PORT = 25575
RCON_PASSWORD = "local-dev-only"
# PaperMC asks every client to identify itself; the default Python agent is refused with a 403.
USER_AGENT = f"craft-arena-bench/{__version__} (https://github.com/yogyam/craft-arena-bench)"


def find_java() -> str:
    """Java 25 or newer: an explicit JAVA_HOME, the Homebrew formula, or whatever `java` is on the path."""
    candidates = []
    if os.environ.get("JAVA_HOME"):
        candidates.append(os.path.join(os.environ["JAVA_HOME"], "bin", "java"))
    candidates += ["/opt/homebrew/opt/openjdk@25/bin/java", "/opt/homebrew/opt/openjdk/bin/java", shutil.which("java") or ""]
    for java in candidates:
        if java and os.path.isfile(java):
            return java
    raise FileNotFoundError("No java found; install Java 25 (brew install openjdk@25) or set JAVA_HOME")


def download_jar(server_dir: Path | None = None) -> Path:
    server_dir = server_dir or repo_root() / "server"
    """Downloads the pinned Paper build if it is not already there with the right checksum."""
    jar = server_dir / "paper.jar"
    if jar.is_file() and _sha256(jar) == PAPER_SHA256:
        return jar
    with urllib.request.urlopen(
        urllib.request.Request(FILL_API.format(version=MINECRAFT_VERSION), headers={"User-Agent": USER_AGENT}), timeout=30
    ) as r:
        builds = json.load(r)
    build = next((b for b in builds if b["id"] == PAPER_BUILD), None)
    if build is None:
        raise RuntimeError(f"Paper {MINECRAFT_VERSION} build {PAPER_BUILD} is not offered by PaperMC any more")
    download = build["downloads"]["server:default"]
    if download["checksums"]["sha256"] != PAPER_SHA256:
        raise RuntimeError("PaperMC's checksum for the pinned build does not match the one pinned here")
    server_dir.mkdir(parents=True, exist_ok=True)
    tmp = jar.with_suffix(".jar.part")
    with (
        urllib.request.urlopen(urllib.request.Request(download["url"], headers={"User-Agent": USER_AGENT}), timeout=60) as r,
        open(tmp, "wb") as f,
    ):
        for chunk in iter(lambda: r.read(1 << 20), b""):
            f.write(chunk)
    if _sha256(tmp) != PAPER_SHA256:
        tmp.unlink()
        raise RuntimeError("The downloaded Paper jar does not match the pinned checksum")
    tmp.replace(jar)
    return jar


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class PaperServer:
    """Runs the server as a child process. `with PaperServer() as s:` starts it and stops it afterwards."""

    def __init__(self, server_dir: Path | None = None, heap: str = "2G", log_name: str = "server.log"):
        self.server_dir = Path(server_dir) if server_dir else repo_root() / "server"
        self.heap = heap
        self.log_path = self.server_dir / log_name
        self.proc: subprocess.Popen | None = None

    def start(self, timeout: float = 120.0) -> None:
        jar = download_jar(self.server_dir)
        (self.server_dir / "eula.txt").write_text("eula=true\n")
        if not (self.server_dir / "server.properties").is_file():
            raise FileNotFoundError(f"{self.server_dir}/server.properties is missing; it is part of the repository")
        log = open(self.log_path, "w")
        self.proc = subprocess.Popen(
            [find_java(), f"-Xms{self.heap}", f"-Xmx{self.heap}", "-XX:+UseG1GC", "-jar", str(jar), "--nogui"],
            cwd=self.server_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"The server exited during start-up; see {self.log_path}")
            try:
                if "Done (" in self.log_path.read_text(errors="replace"):
                    return
            except OSError:
                pass
            time.sleep(0.5)
        self.stop()
        raise TimeoutError(f"The server did not finish starting in {timeout:.0f} s; see {self.log_path}")

    def stop(self, timeout: float = 30.0) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            try:
                with Rcon(port=RCON_PORT, password=RCON_PASSWORD) as rcon:
                    rcon.command("stop")
            except OSError:
                self.proc.terminate()
            try:
                self.proc.wait(timeout)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()


def is_running(port: int = RCON_PORT) -> bool:
    try:
        with Rcon(port=port, password=RCON_PASSWORD, timeout=2.0) as rcon:
            rcon.command("list")
        return True
    except OSError:
        return False
