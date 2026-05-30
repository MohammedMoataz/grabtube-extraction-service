"""POST /resolve — classify a link and return metadata + formats (US1)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..models.domain import ErrorCode, LinkKind
from ..errors import ServiceError
from ..middleware.rate_limit import make_dependency
from ..models.schemas import (
    ResolveRequest,
    ResolvePlaylistResponse,
    ResolveVideoResponse,
    media_item_out,
    playlist_out,
)

router = APIRouter()


@router.post("/resolve")
async def resolve(req: ResolveRequest, request: Request, _rl=Depends(make_dependency("resolve"))):
    resolver = request.app.state.resolver
    settings = request.app.state.settings
    try:
        kind, item, playlist = await asyncio.wait_for(
            resolver.resolve(req.url), timeout=settings.resolve_timeout_s
        )
    except asyncio.TimeoutError as exc:
        raise ServiceError(ErrorCode.timeout) from exc

    if kind is LinkKind.playlist and playlist is not None:
        return JSONResponse(ResolvePlaylistResponse(playlist=playlist_out(playlist)).model_dump())
    return JSONResponse(ResolveVideoResponse(item=media_item_out(item)).model_dump())
