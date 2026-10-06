"""Every manifest committed under submissions/ must load. The maintainer can push there without the pull request check."""

from pathlib import Path

from craft_arena_bench.service.manifests import load_manifest, submission_folders

ROOT = Path(__file__).resolve().parents[1]


def test_every_committed_manifest_loads():
    folders = submission_folders(str(ROOT / "submissions"))
    assert folders, "no submissions found"
    for folder in folders:
        manifest = load_manifest(folder)
        assert manifest.slug == Path(folder).name
