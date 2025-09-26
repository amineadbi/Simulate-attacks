from __future__ import annotations

from fastapi import FastAPI

from .api import build_app

app: FastAPI = build_app()


def get_app() -> FastAPI:
    return app
