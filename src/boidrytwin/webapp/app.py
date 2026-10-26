"""The web app: request rules, view handling and the route modules (contracts/http-api.md).

Request rules (research R8):
- only ``localhost:<port>`` / ``127.0.0.1:<port>`` as ``Host`` (else 421);
- state-changing requests from another origin are refused (403);
- the view (``engineer`` | ``operator``) comes from the ``view`` cookie; pages without it
  redirect to the view choice, API calls get 401; every route is checked against
  :data:`~boidrytwin.webapp.permissions.PERMISSIONS` (403 if not allowed).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.logging import get_logger
from boidrytwin.webapp import i18n
from boidrytwin.webapp.action_log import ActionLog
from boidrytwin.webapp.jobs import JobQueue
from boidrytwin.webapp.permissions import VIEWS, allowed
from boidrytwin.webapp.run_index import RunIndex
from boidrytwin.webapp.settings import AppSettings

HERE = Path(__file__).parent
STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

log = get_logger("webapp")


@dataclass
class Context:
    settings: AppSettings
    index: RunIndex
    actions: ActionLog
    templates: Jinja2Templates

    def queue(self) -> JobQueue:
        return JobQueue(self.settings.app_dir)


def ctx(request: Request) -> Context:
    return request.app.state.ctx  # type: ignore[no-any-return]


def view_of(request: Request) -> str | None:
    view = request.cookies.get("view")
    return view if view in VIEWS else None


class NeedsViewError(Exception):
    pass


def check_view(request: Request) -> None:
    """Global dependency: the route's permission for the request's view (FR-016)."""
    route = request.scope.get("route")
    name = getattr(route, "name", None) or ""
    view = view_of(request)
    if allowed(name, view):
        return
    if view is None:
        raise NeedsViewError()
    raise HTTPException(403, "not allowed in the operator view")


def local_target(path: str) -> str:
    """Only paths on this app: never another host (``//host`` or slash-backslash-host)."""
    ok = path.startswith("/") and not path.startswith(("//", "/\\"))
    return path if ok else "/"


def api_routes(app: FastAPI) -> list[Any]:
    """Every endpoint route of the app, also those inside included routers."""
    from fastapi.routing import APIRoute

    out: list[Any] = []
    stack: list[Any] = list(app.routes)
    while stack:
        route = stack.pop(0)
        if isinstance(route, APIRoute):
            out.append(route)
        inner = getattr(route, "original_router", None) or getattr(route, "router", None)
        if inner is not None and inner is not app.router:
            stack.extend(getattr(inner, "routes", []))
    return out


def plotly_js_path() -> Path:
    import plotly

    return Path(plotly.__file__).parent / "package_data" / "plotly.min.js"


def issues_response(exc: ScenarioValidationError) -> JSONResponse:
    issues = [
        {
            "field": i.field,
            "value": i.value,
            "reason": i.reason,
            "allowed": i.allowed,
            "location": i.location,
        }
        for i in exc.issues
    ]
    return JSONResponse({"issues": issues}, status_code=422)


def create_app(settings: AppSettings) -> FastAPI:
    app = FastAPI(
        title="boidrytwin",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(check_view)],
    )
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.autoescape = True  # also for the SVG drawings (default: .html/.xml only)
    templates.env.globals["view_of"] = view_of
    i18n.install(templates.env)
    app.state.ctx = Context(
        settings=settings,
        index=RunIndex(settings.runs_dir),
        actions=ActionLog(settings.app_dir),
        templates=templates,
    )

    @app.middleware("http")
    async def request_rules(request: Request, call_next: Any) -> Response:
        host = request.headers.get("host", "")
        if host not in settings.allowed_hosts:
            return JSONResponse({"error": "unknown host"}, status_code=421)
        if request.method in STATE_CHANGING:
            origin = request.headers.get("origin")
            if origin is not None and origin not in settings.origins:
                return JSONResponse({"error": "cross-origin request refused"}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"error": "cross-site request refused"}, status_code=403)
        response: Response = await call_next(request)
        return response

    @app.exception_handler(NeedsViewError)
    async def needs_view(request: Request, exc: NeedsViewError) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"error": "choose a view first"}, status_code=401)
        return RedirectResponse("/", status_code=303)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> Response:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(ScenarioValidationError)
    async def scenario_error(request: Request, exc: ScenarioValidationError) -> Response:
        return issues_response(exc)

    @app.exception_handler(RequestValidationError)
    async def request_error(request: Request, exc: RequestValidationError) -> Response:
        issues = [
            {
                "field": ".".join(str(p) for p in e.get("loc", ())),
                "value": str(e.get("input", "")),
                "reason": e.get("msg", ""),
                "allowed": e.get("type", ""),
                "location": None,
            }
            for e in exc.errors()
        ]
        return JSONResponse({"issues": issues}, status_code=422)

    @app.get("/", name="index")
    def index(request: Request) -> Response:
        from boidrytwin.webapp import about
        from boidrytwin.webapp.routes.runs import home_context

        context = {"view": view_of(request), "about": about, **home_context(request)}
        return templates.TemplateResponse(request, "index.html", context)

    @app.post("/view", name="set_view")
    def set_view(view: str = Form(...)) -> Response:
        if view not in VIEWS:
            raise HTTPException(422, "view must be engineer or operator")
        target = "/runs" if view == "engineer" else "/operator"
        response = RedirectResponse(target, status_code=303)
        response.set_cookie("view", view, httponly=True, samesite="strict")
        return response

    @app.get("/view/{view}", name="view_link")
    def view_link(view: str, next: str = "/") -> Response:
        """A bookmarkable link that sets the view, e.g. ``/view/operator?next=/operator``."""
        if view not in VIEWS:
            raise HTTPException(404, "view must be engineer or operator")
        response = RedirectResponse(local_target(next), status_code=303)
        response.set_cookie("view", view, httponly=True, samesite="lax")
        return response

    @app.get("/lang/{lang}", name="lang_link")
    def lang_link(lang: str, next: str = "/") -> Response:
        """Switch the page language (FR-027) and go back, e.g. ``/lang/en?next=/runs``."""
        if lang not in i18n.LANGS:
            raise HTTPException(404, "language must be de or en")
        response = RedirectResponse(local_target(next), status_code=303)
        response.set_cookie("lang", lang, max_age=10 * 365 * 24 * 3600, samesite="lax")
        return response

    @app.get("/static/plotly.min.js", name="plotly_js")
    def plotly_js() -> Response:
        return FileResponse(plotly_js_path(), media_type="text/javascript")

    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    from boidrytwin.webapp import routes

    routes.register(app)
    return app
