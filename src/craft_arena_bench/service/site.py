"""Builds the leaderboard website from the pair results: plain HTML, one board per mode and tier, nothing loaded from
other hosts. The replay viewer is a static page that reads the gzipped replay files in the browser."""

from __future__ import annotations

import datetime
import html
import json
import os
import shutil
from pathlib import Path

from .. import INTERFACE_VERSION, MINECRAFT_VERSION, MODE_SET_VERSION
from . import MATCHES_PER_PAIR, MIN_OPPONENTS, SEASON
from .manifests import MODES, Manifest, load_all
from .pairings import REPLAYS_SUFFIX, board_name, boards, current_documents, load_pair_documents, matches_by_board, pair_name
from .rating import bootstrap_ratings, opponents

REPOSITORY = "https://github.com/yogyam/craft-arena-bench"
MODE_NAMES = {"sumo": "Sumo", "block_uhc": "Block UHC"}
DISCLAIMER = "Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft. CraftArenaBench is free and non-commercial."
CSP = "default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'"

STYLE = """
:root { color-scheme: light; --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781; --grid:#e1e0d9;
  --border:rgba(11,11,11,.10); --wash:rgba(11,11,11,.05); --accent:#2a78d6; --accent-soft:#d5e5f9; --good:#006300; --bad:#b3261e; }
@media (prefers-color-scheme: dark) { :root { color-scheme: dark; --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --border:rgba(255,255,255,.10); --wash:rgba(255,255,255,.07); --accent:#3987e5; --accent-soft:#1c3b63; --good:#0ca30c; --bad:#ff6b63; } }
* { box-sizing: border-box; }
body { margin:0; padding:0 16px 56px; background:var(--page); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1180px; margin:0 auto; }
a { color:var(--accent); }
header { padding:36px 0 20px; display:flex; flex-wrap:wrap; gap:16px 32px; align-items:flex-end; justify-content:space-between; }
header h1 { margin:0; font-size:34px; font-weight:700; letter-spacing:-.01em; }
header p { margin:6px 0 0; color:var(--ink-2); max-width:680px; }
nav { display:flex; flex-wrap:wrap; gap:6px; }
nav a { color:var(--ink); text-decoration:none; padding:7px 12px; border:1px solid var(--border); border-radius:8px; background:var(--surface); font-size:14px; }
nav a.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
h2 { margin:36px 0 10px; font-size:20px; }
h3 { margin:24px 0 8px; font-size:16px; color:var(--ink-2); }
p.lead { margin:0 0 14px; color:var(--ink-2); }
.small { color:var(--muted); font-size:13px; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:6px 0 8px; }
.tile { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:12px 14px; }
.tile .label { color:var(--ink-2); font-size:13px; } .tile .value { font-size:24px; font-weight:600; margin-top:2px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:10px 14px; overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
th, td { padding:8px 7px; text-align:right; border-bottom:1px solid var(--grid); white-space:nowrap; vertical-align:middle; }
th { color:var(--ink-2); font-weight:600; cursor:pointer; user-select:none; font-size:13px; }
th.text, td.text { text-align:left; } tr:last-child td { border-bottom:none; } tbody tr:hover td { background:var(--wash); }
td.rank { color:var(--ink-2); width:40px; } td.rank.top { color:var(--ink); font-weight:700; }
.bot { font-weight:600; } .desc { color:var(--ink-2); font-size:12.5px; white-space:normal; max-width:320px; }
.ci { color:var(--muted); font-size:12px; } .house { font-size:11px; font-weight:600; color:var(--ink-2); background:var(--wash); border-radius:4px; padding:1px 6px; vertical-align:middle; }
.flag { font-size:11px; font-weight:600; color:#8a4b00; background:#fff1dc; border-radius:4px; padding:1px 6px; text-decoration:none; vertical-align:middle; }
.late-bad { color:var(--bad); }
.grid td.win { color:var(--good); font-weight:600; } .grid td.loss { color:var(--bad); } .grid td.self { background:var(--wash); } .grid td a { text-decoration:none; color:inherit; }
.steps { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; }
.step { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }
.step b { display:block; font-size:13px; color:var(--accent); margin-bottom:4px; } .step code { font-size:12.5px; background:var(--wash); padding:2px 6px; border-radius:4px; }
footer { margin-top:44px; color:var(--muted); font-size:12px; }
@media (max-width:640px) { header h1 { font-size:26px; } .desc { max-width:240px; } }
"""

SCRIPT = """
document.querySelectorAll("th[data-sort]").forEach(function (th) {
  th.addEventListener("click", function () {
    var body = th.closest("table").querySelector("tbody");
    var index = Array.prototype.indexOf.call(th.parentNode.children, th);
    var numeric = th.dataset.sort === "number", asc = th.dataset.dir !== "asc";
    th.parentNode.querySelectorAll("th").forEach(function (h) { delete h.dataset.dir; });
    th.dataset.dir = asc ? "asc" : "desc";
    var rows = Array.prototype.slice.call(body.querySelectorAll("tr"));
    rows.sort(function (a, b) {
      var x = a.children[index].dataset.value, y = b.children[index].dataset.value;
      if (numeric) { x = parseFloat(x); y = parseFloat(y); if (isNaN(x)) x = -1e9; if (isNaN(y)) y = -1e9; return asc ? x - y : y - x; }
      return asc ? x.localeCompare(y) : y.localeCompare(x);
    });
    rows.forEach(function (r) { body.appendChild(r); });
  });
});
"""


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def _link(url: str, text: str) -> str:
    if not url.startswith("https://"):
        return _e(text)
    return f'<a href="{_e(url)}" rel="noopener nofollow">{_e(text)}</a>'


def _tiles(items: list[tuple[str, str]]) -> str:
    return (
        '<div class="tiles">'
        + "".join(
            f'<div class="tile"><div class="label">{_e(label)}</div><div class="value">{_e(value)}</div></div>'
            for label, value in items
        )
        + "</div>"
    )


def board_rows(mode: str, hz: int, manifests: dict[str, Manifest], documents: list[dict], flags: dict) -> list[dict]:
    """One row per entrant on the board: rating with interval (or none yet), points, record, latency."""
    by_board = matches_by_board(documents)
    matches = by_board.get((mode, hz), {})
    rated = bootstrap_ratings(matches)
    opp = opponents(matches)
    rows = []
    for slug, m in manifests.items():
        if not m.plays(mode, hz):
            continue
        wins = losses = draws = 0
        latencies, asked, late = [], 0, 0
        for d in documents:
            if (d["mode"], d["tier_hz"]) != (mode, hz) or slug not in (d["a"], d["b"]):
                continue
            side, other = ("a", "b") if d["a"] == slug else ("b", "a")
            wins += d[f"{side}_wins"]
            losses += d[f"{other}_wins"]
            draws += d["draws"]
            lat = d[f"{side}_latency"]
            if lat["median_ms"] is not None:
                latencies.append(lat["median_ms"])
            asked += lat["asked"]
            late += round(lat["late_fraction"] * lat["asked"])
        r = rated.get(slug)
        rows.append(
            {
                "slug": slug,
                "manifest": m,
                "rating": r["rating"] if r and opp.get(slug, 0) >= MIN_OPPONENTS else None,
                "low": r["low"] if r else None,
                "high": r["high"] if r else None,
                "opponents": opp.get(slug, 0),
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "points": wins + 0.5 * draws,
                "played": wins + losses + draws,
                "median_ms": sorted(latencies)[len(latencies) // 2] if latencies else None,
                "late_fraction": late / asked if asked else None,
                "flag": flags.get(slug),
            }
        )
    rows.sort(key=lambda r: (r["rating"] is None, -(r["rating"] or 0), -r["points"], r["slug"]))
    return rows


def render_board_table(rows: list[dict]) -> str:
    head = (
        '<thead><tr><th>#</th><th class="text" data-sort="text">Bot</th><th data-sort="number">Rating</th><th data-sort="number">Points</th>'
        '<th data-sort="number">W-L-D</th><th data-sort="number">Opponents</th><th data-sort="number">Latency</th><th data-sort="number">Late</th>'
        '<th class="text" data-sort="text">Author</th><th class="text">What it is</th></tr></thead>'
    )
    body = []
    for i, r in enumerate(rows, 1):
        m = r["manifest"]
        rating = (
            f'{r["rating"]:.0f} <span class="ci">{r["low"]:.0f}–{r["high"]:.0f}</span>'
            if r["rating"] is not None
            else f'<span class="small">needs {MIN_OPPONENTS} opponents</span>'
        )
        name = f'<span class="bot">{_link(m.homepage, m.name) if m.homepage else _e(m.name)}</span>'
        if m.house:
            name += ' <span class="house">house</span>'
        if r["flag"]:
            name += f' <a class="flag" href="{_e(r["flag"])}" rel="noopener">Flagged</a>'
        lat = f"{r['median_ms']:.0f} ms" if r["median_ms"] is not None else "–"
        late = f"{r['late_fraction']:.1%}" if r["late_fraction"] is not None else "–"
        late_class = ' class="late-bad"' if (r["late_fraction"] or 0) > 0.05 else ""
        body.append(
            f'<tr><td class="rank{" top" if i <= 3 and r["rating"] is not None else ""}">{i}</td>'
            f'<td class="text" data-value="{_e(m.name.lower())}">{name}</td>'
            f'<td data-value="{r["rating"] if r["rating"] is not None else -1}">{rating}</td>'
            f'<td data-value="{r["points"]}">{r["points"]:g} / {r["played"]}</td>'
            f'<td data-value="{r["wins"]}">{r["wins"]}-{r["losses"]}-{r["draws"]}</td>'
            f'<td data-value="{r["opponents"]}">{r["opponents"]}</td>'
            f'<td data-value="{r["median_ms"] if r["median_ms"] is not None else -1}">{lat}</td>'
            f'<td data-value="{r["late_fraction"] if r["late_fraction"] is not None else -1}"{late_class}>{late}</td>'
            f'<td class="text" data-value="{_e(m.author.lower())}">{_e(m.author)}</td>'
            f'<td class="text desc">{_e(m.description)}</td></tr>'
        )
    return f'<div class="card"><table>{head}<tbody>{"".join(body)}</tbody></table></div>'


def render_grid(mode: str, hz: int, rows: list[dict], documents: list[dict]) -> str:
    """Who beat whom: a's points against b in each cell, linking to the replay."""
    slugs = [r["slug"] for r in rows]
    names = {r["slug"]: r["manifest"].name for r in rows}
    results = {}
    for d in documents:
        if (d["mode"], d["tier_hz"]) == (mode, hz):
            results[(d["a"], d["b"])] = (d["a_points"], d["b_points"])
            results[(d["b"], d["a"])] = (d["b_points"], d["a_points"])
    if len(slugs) < 2:
        return ""
    head = (
        '<thead><tr><th class="text"></th>'
        + "".join(f'<th title="{_e(names[s])}">{_e(names[s][:12])}</th>' for s in slugs)
        + "</tr></thead>"
    )
    body = []
    for a in slugs:
        cells = []
        for b in slugs:
            if a == b:
                cells.append('<td class="self"></td>')
                continue
            if (a, b) not in results:
                cells.append('<td class="small">–</td>')
                continue
            pa, pb = results[(a, b)]
            cls = "win" if pa > pb else "loss" if pa < pb else ""
            href = f"replay.html?board={board_name(mode, hz)}&amp;pair={pair_name(a, b)}"
            cells.append(
                f'<td class="{cls}"><a href="{href}" title="{_e(names[a])} {pa:g} – {pb:g} {_e(names[b])}, watch">{pa:g}–{pb:g}</a></td>'
            )
        body.append(f'<tr><td class="text bot">{_e(names[a])}</td>{"".join(cells)}</tr>')
    return f'<h3>Pairings: points taken, row against column (click to watch)</h3><div class="card"><table class="grid">{head}<tbody>{"".join(body)}</tbody></table></div>'


def render(manifests: dict[str, Manifest], documents: list[dict], flags: dict) -> str:
    total_matches = sum(len(d["matches"]) for d in documents)
    total_decisions = sum(m["decisions"] for d in documents for m in d["matches"])
    entrants = sum(1 for m in manifests.values() if not m.house)
    sections = []
    for mode, hz in boards():
        rows = board_rows(mode, hz, manifests, documents, flags)
        if not rows:
            continue
        played = sum(1 for d in documents if (d["mode"], d["tier_hz"]) == (mode, hz))
        sections.append(
            f'<h2 id="{board_name(mode, hz)}">{_e(MODE_NAMES[mode])} at {hz} decisions per second</h2>'
            f'<p class="lead">{len(rows)} bots, {played} pairs played, {MATCHES_PER_PAIR} matches per pair, half on each spawn side. '
            f"Rating is Bradley-Terry over points (a win is a point, a draw half) with a 95% bootstrap interval; shown after {MIN_OPPONENTS} opponents. "
            f"Latency is the endpoint's median answer time; late answers keep the previous intent.</p>"
            + render_board_table(rows)
            + render_grid(mode, hz, rows, documents)
        )
    if not sections:
        sections.append(
            '<h2>No results yet</h2><p class="lead">The first pairs are played after the first submissions are merged.</p>'
        )
    nav = "".join(f'<a href="#{board_name(mode, hz)}">{_e(MODE_NAMES[mode])} {hz} Hz</a>' for mode, hz in boards())
    steps = (
        '<div class="steps">'
        '<div class="step"><b>1. Host an endpoint</b>Any model, anywhere. Answer <code>GET /health</code> and <code>POST /decide</code> as in <a href="'
        + REPOSITORY
        + '/blob/main/docs/INTERFACE.md">INTERFACE.md</a>. The adapters folder has working examples, including one for a local Ollama model.</div>'
        '<div class="step"><b>2. Try it at home</b>Run the harness against your endpoint on your own server: <code>craft-arena-bench play --b https://…</code></div>'
        '<div class="step"><b>3. Open a pull request</b>Add <code>submissions/&lt;slug&gt;/submission.json</code> naming your bot, your GitHub login, the endpoint, and the tiers and modes you enter. See <a href="'
        + REPOSITORY
        + '/blob/main/docs/SUBMITTING.md">SUBMITTING.md</a>.</div>'
        '<div class="step"><b>4. Keep it up</b>The scoring service plays your pairs on a weekly run and whenever a submission is merged. Ratings, intervals and replays appear here.</div>'
        "</div>"
    )
    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<title>CraftArenaBench</title><style>{STYLE}</style></head>
<body><main>
<header><div><h1>CraftArenaBench</h1><p>An AI-vs-AI benchmark for Minecraft decision models. Models fight in PvP arenas through a shared body, at a fixed number of decisions per second, and are rated per mode and tier.</p></div>
<nav>{nav}<a class="primary" href="{REPOSITORY}">Enter a bot</a><a href="{REPOSITORY}/blob/main/RULES.md">Rules</a></nav></header>
{_tiles([("Entrants", str(entrants)), ("House bots", str(len(manifests) - entrants)), ("Matches played", f"{total_matches:,}"), ("Decisions asked", f"{total_decisions:,}"), ("Season", str(SEASON))])}
{"".join(sections)}
<h2>Enter your bot</h2>{steps}
<footer><p>Season {SEASON}, interface version {INTERFACE_VERSION}, mode set version {MODE_SET_VERSION}, Minecraft {MINECRAFT_VERSION}. Built {now}. Source and rules at <a href="{REPOSITORY}">{REPOSITORY.removeprefix("https://")}</a>.</p>
<p>{DISCLAIMER}</p></footer>
</main><script src="site.js"></script></body></html>
"""


def load_flags(path: str) -> dict:
    if not path or not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        flags = json.load(f)
    return {k: v for k, v in flags.items() if isinstance(k, str) and isinstance(v, str) and v.startswith("https://")}


def build_site(
    submissions_folder: str, duels_folder: str, replays_folder: str, output_folder: str, flags_path: str = "flags.json"
) -> str:
    manifests = load_all(submissions_folder)
    documents = current_documents(load_pair_documents(duels_folder), manifests, submissions_folder)
    out = Path(output_folder)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render(manifests, documents, load_flags(flags_path)), encoding="utf-8")
    (out / "site.js").write_text(SCRIPT, encoding="utf-8")
    (out / "replay.html").write_text(
        (Path(__file__).parent / "replay.html").read_text(encoding="utf-8").replace("__CSP__", CSP), encoding="utf-8"
    )
    (out / "replay.js").write_text((Path(__file__).parent / "replay.js").read_text(encoding="utf-8"), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    # Replays: only those of current pairs, so a stale file never lingers on the site.
    current = {(d["mode"], d["tier_hz"], pair_name(d["a"], d["b"])) for d in documents}
    for mode, hz, pair in current:
        src = Path(replays_folder) / board_name(mode, hz) / f"{pair}{REPLAYS_SUFFIX}"
        if src.is_file():
            dst = out / "replays" / board_name(mode, hz) / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    (out / "boards.json").write_text(
        json.dumps({"boards": [board_name(m, h) for m, h in boards()], "modes": MODES}), encoding="utf-8"
    )
    return str(out / "index.html")
