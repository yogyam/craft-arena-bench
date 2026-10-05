# Contributing

Thanks for taking an interest. Two kinds of contribution come in through pull requests, and they are handled differently.

## Entering a bot

That is a submission, not a code change: see [docs/SUBMITTING.md](docs/SUBMITTING.md). A submission pull request changes only `submissions/<slug>/submission.json` and is merged once its check passes.

## Changing the project

Bug reports and ideas go in [issues](https://github.com/yogyam/craft-arena-bench/issues); there are templates for a submission problem and for mode, interface or rules feedback. For a change of any size beyond a typo, open an issue first so the shape of it can be agreed before you spend time on it.

### Setting up

See [docs/SETUP.md](docs/SETUP.md) for the Java, Node and Paper server setup. The Python part:

```bash
git clone https://github.com/yogyam/craft-arena-bench.git
cd craft-arena-bench
pip install -e ".[dev]"
pytest -q
ruff check src tests && ruff format --check src tests
```

### What a pull request needs

- Tests for what it changes. The suite is the project's evidence that scoring is fair.
- `ruff check` and `ruff format` clean.
- Prose in the style of the existing docs: short, concrete, and honest about limits.

### Changes that affect ratings

Some changes make old results incomparable with new ones. Each has a version number that must be bumped, and a changelog entry:

| Change | Bump |
|---|---|
| What a model is told, the action lists, the tier budgets, the late-answer rules, the reflex layer | `INTERFACE_VERSION` |
| An arena, a mode's items, time caps or win rule | `MODE_SET_VERSION` |
| The Minecraft or Paper version, the matches per pair, the arena seeds, the house bot | A new season |

A new interface version starts a new leaderboard and archives the old one. Propose such changes in an issue first; they are announced before they take effect.

## Code of conduct

Everyone taking part is expected to follow the [code of conduct](CODE_OF_CONDUCT.md).
