# Contributing

Thanks for your interest in improving DocFormatConverter! 🎉

## Ground rules

* Be respectful. See [the Contributor Covenant](https://www.contributor-covenant.org/).
* Don't commit secrets, API keys, or production data.
* Don't open a PR that touches the public HTTP API without writing
  the corresponding test and documentation.
* Don't add a new runtime dependency without discussing it first.

## Local setup

```bash
git clone https://github.com/badhope/DocFormatConverter.git
cd DocFormatConverter
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
docker compose -f docker-compose.dev.yml up
```

## Workflow

1. Fork the repo.
2. Create a branch: `git checkout -b feat/my-feature`
3. Make your changes.
4. `pre-commit run --all-files` (formatting, lint, secrets)
5. `make test` (full pytest suite)
6. `make lint`
7. Push and open a PR. Fill out the template.

## Code style

* Python: `black` + `isort` + `ruff` (enforced by pre-commit).
  Type hints on every public function. `mypy --strict` for new modules.
* TypeScript: `prettier` + `eslint`. `tsc --strict`.
* No trailing whitespace, no commented-out code, no `print()`
  debugging in committed code.

## Adding a new converter

1. Find or create a category under `backend/app/converters/`
   (`documents/`, `images/`, `markup/`, `data/`, `ebooks/`).
2. Write a class subclassing `BaseConverter`:

```python
from app.converters.base import BaseConverter
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult

class FooBarConverter(BaseConverter):
    inputs = {"foo"}
    outputs = {"bar"}
    backend = "my-tool"

    async def convert(self, src, dst, options: ConversionOptions) -> ConversionResult:
        # ...
        return ConversionResult(output=dst, output_format="bar", backend=self.backend)
```

3. Drop it in the file — the registry auto-discovers it on first
   call to `get_registry()`. No central registration needed.
4. Add a test in `backend/tests/test_format_registry.py`.
5. Add a fixture in `backend/tests/fixtures/` (small sample input).
6. Document the new conversion in `docs/api.md` (`/v1/formats/convertible`).

## Releasing

1. Bump the version in `pyproject.toml` and `frontend/package.json`.
2. Update `CHANGELOG.md`.
3. Tag: `git tag -s v1.2.3 -m "Release 1.2.3"`
4. Push: `git push --follow-tags`
5. The release workflow builds & pushes images to GHCR, drafts a
   GitHub release with auto-generated notes.

## Security

Found a vulnerability? Email `security@docformatconverter.example.com`
(do not open a public issue). See [docs/security.md](docs/security.md).
