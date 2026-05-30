"""Configurable CORS allow-list (FR-014).

Only the explicit operator-supplied origins are granted CORS; non-listed origins are not.
No client-embedded secret is used.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def add_cors(app: FastAPI, origins: list[str]) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,  # empty list => no cross-origin granted
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
