"""Jinja2 template loader/renderer for design artifacts."""
from __future__ import annotations
from importlib.resources import files
from jinja2 import Environment, BaseLoader, TemplateNotFound, select_autoescape


class _PackageLoader(BaseLoader):
    """Loads templates from the `_templates/` resource dir of this package."""

    def get_source(self, environment, template):
        try:
            data = (files("project_cli") / "_templates" / template).read_text()
        except FileNotFoundError as e:
            raise TemplateNotFound(template) from e
        return data, template, lambda: True


_env = Environment(
    loader=_PackageLoader(),
    autoescape=select_autoescape(default=False),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template: str, **context) -> str:
    return _env.get_template(template).render(**context)
