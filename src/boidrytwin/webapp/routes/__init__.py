"""Route modules of the web app, one per user story."""

from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI) -> None:
    for name in ("runs", "scenarios", "operator", "comparisons", "showcase"):
        try:
            module = __import__(f"boidrytwin.webapp.routes.{name}", fromlist=["router"])
        except ModuleNotFoundError as exc:
            if exc.name != f"boidrytwin.webapp.routes.{name}":
                raise
            continue  # story not implemented yet
        app.include_router(module.router)
