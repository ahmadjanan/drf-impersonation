# Contributing

## Development setup

You need [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ahmadjanan/drf-impersonation.git
cd drf-impersonation
uv sync --extra test --extra lint
```

## Checks

CI runs all of these. Run them before you open a pull request:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov        # coverage must stay at 100%
```

To test against a specific Python, Django and DRF:

```bash
uv run --no-project --python 3.13 \
  --with "Django~=6.1.0" --with "djangorestframework~=3.18.0" \
  --with drf-spectacular --with pytest --with pytest-django \
  -- python -m pytest
```

## Pull requests

- Add a test for every behaviour change.
- Add an entry under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
- Keep pull requests to one change each.

## Releasing

Releases are published to PyPI from GitHub Actions with
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/), so no API token is stored
anywhere.

1. Update `__version__` in `src/drf_impersonation/__init__.py`. Follow
   [Semantic Versioning](https://semver.org/).
2. In `CHANGELOG.md`, move the `Unreleased` entries under a new version heading with today's
   date. Update the compare links at the bottom.
3. Commit, then tag and push:
   ```bash
   git tag v0.2.0
   git push origin main v0.2.0
   ```

The [release workflow](.github/workflows/release.yml) runs the full CI and checks that the tag
matches `__version__`. Then it builds the sdist and wheel, publishes them to PyPI and creates a
GitHub release with the built files attached.

### One-time setup

1. On PyPI, add a trusted publisher for repository `ahmadjanan/drf-impersonation`, workflow
   `release.yml` and environment `pypi`. Before the first release, add it as a *pending*
   publisher.
2. In the GitHub repository settings, create an environment named `pypi`. Add required reviewers
   to it if you want a manual approval before each upload.
