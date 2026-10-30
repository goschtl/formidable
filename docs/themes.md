# Themes

A `Theme` bundles what a CSS framework needs: class names for every element,
template and widget overrides, and asset URLs. Bootstrap 5 and Materialize ship
with formidable.

```python
from formidable import themes
from formidable.themes.bootstrap import BOOTSTRAP
from formidable.themes.material import MATERIAL

themes.use(BOOTSTRAP)                  # the site-wide default, once at startup


class Admin(Form):
    theme = MATERIAL                   # for one view

    def get_theme(self, request):      # or per request, for multi-tenant sites
        ...
```

`page(html_form, theme, title=...)` wraps a form in a full HTML page with the
theme's stylesheets and scripts. Without a theme, the output is clean HTML with
stable classes that you can style yourself.

Besides the class names for fields, `summary` styles the [error
summary](accessibility.md), `status` a message such as "saved", and `steps`,
`step`, `step_link` and `step_current` the list of [steps](wizard.md).

## Writing a theme

`src/formidable/themes/bootstrap.py` is a complete example and only about 30
lines. Set class names on a `Theme`, and add `templates` where class names
aren't enough.
