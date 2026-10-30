# Development

```bash
uv sync
uv run pytest
uvx ruff check src/ tests/ ex.py
cd tests/js && npm install && npm test     # the browser scripts
```

Built on Pydantic v2, chameleon-rs, beartype and werkzeug.

## This documentation

The pages are in `docs/`. To preview them:

```bash
uvx --from "mkdocs<2" --with mkdocs-material mkdocs serve
```

A push that changes them publishes the site to GitHub Pages, through the
`Docs` workflow and the `gh-pages` branch.

## Bundled FilePond

`src/formidable/static/filepond/` holds unmodified files from npm, with their
versions in `VERSIONS`. To update them, replace the files and update that list.
