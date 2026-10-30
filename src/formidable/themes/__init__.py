"""Themes: self-contained styling plugins.

A Theme bundles everything a CSS framework integration needs:

* class names the built-in renderers apply,
* structural widget overrides (`widgets`) for markup a framework
  requires (e.g. Bootstrap's form-check checkboxes),
* asset URLs (`stylesheets`, `scripts`) consumed by `page()`.

Concrete themes live in their own submodule (one plugin per module,
e.g. `formidable.themes.bootstrap`) so the base package stays free of
renderer imports. Functional classes the JS and tests rely on
(`field-error`, `field-list-item`, `formidable-add-row`, ...) are
always present regardless of theme.
"""

import typing as t
from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class Theme:
    form: str = ""          # the <form> tag
    wrapper: str = ""       # the <div> wrapping label + input
    label: str = ""
    input: str = ""         # text/number/file inputs
    select: str = ""
    checkbox: str = ""
    invalid: str = ""       # added to an input that has an error
    error: str = ""         # added to the error <span>
    hint: str = ""          # added to hint <span>s (e.g. lost upload)
    fieldset: str = ""      # nested models and lists
    legend: str = ""
    button: str = ""        # trigger (submit) buttons
    row_button: str = ""    # the JS add/remove row buttons
    container: str = ""     # the <main> wrapper used by page()
    widgets: t.Mapping = ()          # structural widget overrides
    stylesheets: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()


DEFAULT = Theme()

_current: Theme = DEFAULT


def use(theme: Theme) -> Theme:
    """Register the site-wide default theme (call once at app startup).

    Returns the previously registered theme, handy for restoring it.
    """
    global _current
    previous = _current
    _current = theme
    return previous


def current() -> Theme:
    """The site-wide default theme."""
    return _current


def page(html_form, theme: Theme = DEFAULT, title: str = "") -> str:
    """Wrap a rendered form in a full HTML page with the theme's assets."""
    links = "\n  ".join(
        f'<link href="{href}" rel="stylesheet">' for href in theme.stylesheets)
    scripts = "\n  ".join(
        f'<script src="{src}"></script>' for src in theme.scripts)
    main_attr = f' class="{theme.container}"' if theme.container else ""
    body = html_form.render() if hasattr(html_form, "render") \
        else str(html_form)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  {links}
</head>
<body>
  <main{main_attr}>
    {body}
  </main>
  {scripts}
</body>
</html>"""
