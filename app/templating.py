"""Shared Jinja2 templates instance and HTMX partial rendering."""

import logging

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.services.league_context import NoLeagueError

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")


def render_partial(request: Request, template: str, build, defaults: dict):
    """Render an HTMX partial, turning failures into an inline error message.

    `build` returns the template context; `defaults` fills the context when
    it fails so the template can still render.
    """
    try:
        context = build()
    except NoLeagueError as e:
        context = {**defaults, "error": str(e)}
    except Exception as e:
        logger.exception("Error rendering %s", template)
        context = {**defaults, "error": str(e)}
    return templates.TemplateResponse(template, {"request": request, **context})
