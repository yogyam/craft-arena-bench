"""Submissions: a manifest per bot, checked strictly, and the pull request checks around it.

A submission is a folder `submissions/<slug>/` holding one file, `submission.json`. It names the bot and its
endpoint; the scoring service calls the endpoint and never runs or downloads anything of the entrant's.
"""

from __future__ import annotations

import datetime
import hashlib
import ipaddress
import json
import os
import re
import socket
import urllib.parse
from dataclasses import dataclass, field

from .. import INTERFACE_VERSION
from ..tiers import TIERS

MANIFEST_NAME = "submission.json"
MODES = ("sumo", "block_uhc")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
GITHUB_LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
MAX_NAME = 40
MAX_TEXT = 300
SUBMISSIONS_PER_PERIOD = 3  # New bots and updates one person may submit in a period, see RULES.md
SUBMISSION_PERIOD_DAYS = 30
BOTS_PER_PERSON = 3
HOUSE_ENDPOINT_PREFIX = "local:"  # The maintainers' house bots run in-process; nobody else may use this
ALLOW_LOCAL = False  # Dry runs only: the CLI's --allow-local accepts http://127.0.0.1 endpoints. Never set on the service.


class SubmissionError(Exception):
    """Something about the submission is not right. The message says what."""


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not SLUG_PATTERN.match(slug):
        raise SubmissionError("The bot name must contain at least one letter or digit")
    return slug[:MAX_NAME].rstrip("-")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Manifest:
    name: str
    slug: str
    author: str
    github: str  # The GitHub login that opens the pull request
    endpoint: str  # https://... ; the harness calls <endpoint>/health and <endpoint>/decide
    tiers: list  # decision rates entered, e.g. [2, 5]
    modes: list  # e.g. ["sumo", "block_uhc"]
    interface_version: int
    submitted: str  # Date, YYYY-MM-DD
    description: str = ""  # What is behind the endpoint: model, size, where it runs
    homepage: str = ""
    house: bool = False  # The maintainers' scripted reference bot; exempt from limits, marked on the board

    REQUIRED = frozenset({"name", "slug", "author", "github", "endpoint", "tiers", "modes", "interface_version", "submitted"})
    OPTIONAL = frozenset({"description", "homepage", "house"})

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        if not d["house"]:
            del d["house"]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Manifest:
        if not isinstance(data, dict):
            raise SubmissionError("The manifest must be a JSON object")
        missing = cls.REQUIRED - set(data)
        unknown = set(data) - cls.REQUIRED - cls.OPTIONAL
        if missing:
            raise SubmissionError(f"The manifest is missing: {', '.join(sorted(missing))}")
        if unknown:
            raise SubmissionError(f"The manifest has fields that are not allowed: {', '.join(sorted(unknown))}")
        manifest = cls(**data)
        manifest.validate()
        return manifest

    def validate(self) -> None:
        for name in ("name", "slug", "author", "github", "endpoint", "submitted", "description", "homepage"):
            if not isinstance(getattr(self, name), str):
                raise SubmissionError(f"'{name}' must be text")
        if type(self.house) is not bool:
            raise SubmissionError("'house' must be true or false")
        if not (1 <= len(self.name) <= MAX_NAME) or self.name != self.name.strip():
            raise SubmissionError(f"The bot name must be 1 to {MAX_NAME} characters, without spaces at the ends")
        if not (1 <= len(self.author) <= MAX_NAME) or not self.author.strip():
            raise SubmissionError(f"The author must be 1 to {MAX_NAME} characters")
        if not GITHUB_LOGIN_PATTERN.match(self.github):
            raise SubmissionError("'github' must be the GitHub login of the person submitting")
        for name in ("description", "homepage"):
            if len(getattr(self, name)) > MAX_TEXT:
                raise SubmissionError(f"'{name}' must be at most {MAX_TEXT} characters")
        if not SLUG_PATTERN.match(self.slug) or len(self.slug) > MAX_NAME:
            raise SubmissionError("The slug must be lowercase letters, digits and single hyphens")
        if self.homepage and not self.homepage.startswith("https://"):
            raise SubmissionError("'homepage' must be an https:// address")
        if self.house:
            if not self.endpoint.startswith(HOUSE_ENDPOINT_PREFIX):
                raise SubmissionError("A house bot's endpoint must be local:<policy>")
        else:
            check_endpoint_url(self.endpoint, allow_local=ALLOW_LOCAL)
        if not isinstance(self.tiers, list) or not self.tiers or len(set(self.tiers)) != len(self.tiers):
            raise SubmissionError("'tiers' must be a non-empty list of distinct decision rates")
        for hz in self.tiers:
            if type(hz) is not int or hz not in TIERS:
                raise SubmissionError(f"'tiers' may only hold {sorted(TIERS)}, not {hz!r}")
            if not TIERS[hz].open_in_season_1:
                raise SubmissionError(f"The {hz} Hz tier is not open this season")
        if not isinstance(self.modes, list) or not self.modes or len(set(self.modes)) != len(self.modes):
            raise SubmissionError("'modes' must be a non-empty list of distinct modes")
        for mode in self.modes:
            if mode not in MODES:
                raise SubmissionError(f"'modes' may only hold {list(MODES)}, not {mode!r}")
        if self.interface_version != INTERFACE_VERSION:
            raise SubmissionError(f"Interface version {self.interface_version} is not the current version {INTERFACE_VERSION}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.submitted):
            raise SubmissionError("'submitted' must be a date, YYYY-MM-DD")

    def plays(self, mode: str, hz: int) -> bool:
        return mode in self.modes and hz in self.tiers


def check_endpoint_url(url: str, allow_local: bool = False) -> None:
    """https only, a hostname, nothing else in the way. `allow_local` is for tests and dry runs (http://127.0.0.1)."""
    parsed = urllib.parse.urlparse(url)
    if allow_local and parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"):
        return
    if parsed.scheme != "https" or not parsed.hostname:
        raise SubmissionError("'endpoint' must be an https:// address")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise SubmissionError(
            "'endpoint' may not carry a query, fragment or credentials; put a token in the path if you need one"
        )
    if len(url) > MAX_TEXT:
        raise SubmissionError(f"'endpoint' must be at most {MAX_TEXT} characters")


def is_public_host(host: str) -> bool:
    """Only public addresses are called: nothing on the scoring machine or its network."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    return bool(infos) and all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


def load_manifest(folder: str) -> Manifest:
    path = os.path.join(folder, MANIFEST_NAME)
    if not os.path.isfile(path):
        raise SubmissionError(f"No {MANIFEST_NAME} in {folder}")
    others = [name for name in os.listdir(folder) if name != MANIFEST_NAME and not name.startswith(".")]
    if others:
        raise SubmissionError(f"A submission folder may only hold {MANIFEST_NAME}, found: {', '.join(others)}")
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise SubmissionError(f"{MANIFEST_NAME} is not valid JSON: {e}") from None
    manifest = Manifest.from_dict(data)
    folder_name = os.path.basename(os.path.normpath(folder))
    if manifest.slug != folder_name:
        raise SubmissionError(f"The folder is named '{folder_name}' but the slug is '{manifest.slug}'")
    return manifest


def manifest_digest(folder: str) -> str:
    with open(os.path.join(folder, MANIFEST_NAME), "rb") as f:
        return sha256(f.read())


def submission_folders(submissions_folder: str) -> list[str]:
    """Every submission folder, by slug, skipping anything that is not named like one."""
    if not os.path.isdir(submissions_folder):
        return []
    return [
        os.path.join(submissions_folder, slug)
        for slug in sorted(os.listdir(submissions_folder))
        if SLUG_PATTERN.match(slug) and os.path.isdir(os.path.join(submissions_folder, slug))
    ]


def load_all(submissions_folder: str) -> dict[str, Manifest]:
    """Every loadable manifest by slug. A broken manifest is skipped: it was refused at its pull request."""
    manifests = {}
    for folder in submission_folders(submissions_folder):
        try:
            manifests[os.path.basename(folder)] = load_manifest(folder)
        except SubmissionError:
            continue
    return manifests


def write_manifest(manifest: Manifest, submissions_folder: str) -> str:
    folder = os.path.join(submissions_folder, manifest.slug)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, MANIFEST_NAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2)
        f.write("\n")
    return path


def new_manifest(
    name: str,
    author: str,
    github: str,
    endpoint: str,
    tiers: list,
    modes: list,
    description: str = "",
    homepage: str = "",
    house: bool = False,
) -> Manifest:
    manifest = Manifest(
        name=name.strip(),
        slug=slugify(name),
        author=author.strip(),
        github=github.strip(),
        endpoint=endpoint.strip(),
        tiers=sorted(tiers),
        modes=[m for m in MODES if m in modes],
        interface_version=INTERFACE_VERSION,
        submitted=datetime.date.today().isoformat(),
        description=description.strip(),
        homepage=homepage.strip(),
        house=house,
    )
    manifest.validate()
    return manifest


# ---- Pull request checks ----


def check_not_a_copy(manifest: Manifest, submissions_folder: str) -> None:
    """A manifest may not point at another submission's endpoint or reuse its name."""
    for other_folder in submission_folders(submissions_folder):
        other_slug = os.path.basename(other_folder)
        if other_slug == manifest.slug:
            continue
        try:
            with open(os.path.join(other_folder, MANIFEST_NAME), encoding="utf-8") as f:
                other = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(other, dict):
            continue
        if manifest.endpoint.rstrip("/").lower() == str(other.get("endpoint", "")).rstrip("/").lower():
            raise SubmissionError(f"This endpoint is already submitted as '{other_slug}'")
        if manifest.name.strip().lower() == str(other.get("name", "")).strip().lower():
            raise SubmissionError(f"The name '{manifest.name}' is already used by '{other_slug}'")


def check_pull_request(
    folders: list, github_login: str, submissions_folder: str, exempt: tuple = (), today: datetime.date | None = None
) -> list[Manifest]:
    """What the pull request check knows that the manifest alone does not: who opened it, and what they already have.

    `exempt` logins (the maintainers, for the house bots) are not held to the limits.
    """
    if not GITHUB_LOGIN_PATTERN.match(github_login or ""):
        raise SubmissionError("The pull request author is not a valid GitHub login")
    manifests = []
    for folder in folders:
        manifest = load_manifest(folder)
        if manifest.github.lower() != github_login.lower():
            raise SubmissionError(
                f"{manifest.slug}: the manifest names '{manifest.github}' but the pull request is from '{github_login}'"
            )
        if manifest.house and github_login.lower() not in {e.lower() for e in exempt}:
            raise SubmissionError(f"{manifest.slug}: only the maintainers may submit a house bot")
        check_not_a_copy(manifest, submissions_folder)
        manifests.append(manifest)
    if github_login.lower() in {login.lower() for login in exempt}:
        return manifests

    changed = {m.slug for m in manifests}
    today = today or datetime.date.today()
    since = today - datetime.timedelta(days=SUBMISSION_PERIOD_DAYS)
    others = [
        m for slug, m in load_all(submissions_folder).items() if slug not in changed and m.github.lower() == github_login.lower()
    ]
    if len(others) + len(changed) > BOTS_PER_PERSON:
        raise SubmissionError(
            f"'{github_login}' would have {len(others) + len(changed)} bots on the board, the limit is {BOTS_PER_PERSON}"
        )
    recent = sum(1 for m in others if datetime.date.fromisoformat(m.submitted) >= since)
    if recent + len(changed) > SUBMISSIONS_PER_PERIOD:
        raise SubmissionError(
            f"'{github_login}' would have {recent + len(changed)} submissions in {SUBMISSION_PERIOD_DAYS} days, the limit is {SUBMISSIONS_PER_PERIOD}"
        )
    return manifests


@dataclass
class HealthReport:
    ok: bool
    detail: str
    doc: dict = field(default_factory=dict)


async def health_check(manifest: Manifest, allow_local: bool = False) -> HealthReport:
    """GET <endpoint>/health must answer 200 with the current interface version. Public hosts only."""
    from ..endpoint import EndpointDecider

    if manifest.house:
        return HealthReport(True, "house bot, runs in-process")
    parsed = urllib.parse.urlparse(manifest.endpoint)
    if not (allow_local or ALLOW_LOCAL) and not is_public_host(parsed.hostname or ""):
        return HealthReport(False, "the endpoint's host is not a public address")
    decider = EndpointDecider(manifest.endpoint, manifest.slug)
    try:
        doc = await decider.health()
        return HealthReport(True, f"health ok, name {doc.get('name')!r}", doc)
    except Exception as e:
        return HealthReport(False, f"health check failed: {type(e).__name__}: {str(e)[:120]}")
    finally:
        await decider.close()
