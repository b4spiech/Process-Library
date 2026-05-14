import base64
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from routers import kpis, library, nodes, sustainability


# Paths exempt from Basic Auth. Railway's healthcheck must stay open.
_AUTH_EXEMPT_PATHS = frozenset({"/health"})
_AUTH_REALM = "Business Process Repository"


def _auth_challenge(detail: str = "Authentication required") -> Response:
    """401 response that triggers the browser's Basic-Auth login prompt."""
    return Response(
        content=detail,
        status_code=401,
        media_type="text/plain",
        headers={"WWW-Authenticate": f'Basic realm="{_AUTH_REALM}"'},
    )


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Require HTTP Basic Auth on every request except /health.

    Credentials are pulled from ADMIN_USERNAME / ADMIN_PASSWORD env vars.
    Comparisons use `secrets.compare_digest` to dodge timing attacks. If
    the env vars aren't set we fail closed (401) so an unconfigured deploy
    can't silently expose the app.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _AUTH_EXEMPT_PATHS:
            return await call_next(request)

        expected_user = os.getenv("ADMIN_USERNAME") or ""
        expected_pass = os.getenv("ADMIN_PASSWORD") or ""
        if not expected_user or not expected_pass:
            return _auth_challenge("Authentication is not configured on this server.")

        header = request.headers.get("authorization", "")
        scheme, _, encoded = header.partition(" ")
        if scheme.lower() != "basic" or not encoded:
            return _auth_challenge()

        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except Exception:
            return _auth_challenge()

        user, _, password = decoded.partition(":")
        # Always compare both fields so the cost is constant regardless of
        # which one was wrong — defeats username enumeration via timing.
        user_ok = secrets.compare_digest(user.encode(), expected_user.encode())
        pass_ok = secrets.compare_digest(password.encode(), expected_pass.encode())
        if not (user_ok and pass_ok):
            return _auth_challenge()

        return await call_next(request)


app = FastAPI(
    title="Business Process Repository",
    description="Phase 1 of The Kendall Group Business Operating System (BOS).",
    version="0.1.0",
)

# Add middleware bottom-up: the LAST one added is the OUTERMOST layer.
# Order on the wire:
#   request  →  CORS  →  BasicAuth  →  app
#   response ←  CORS  ←  BasicAuth  ←  app
# This means CORS handles preflight OPTIONS without ever hitting auth,
# while every real route goes through auth.
app.add_middleware(BasicAuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


app.include_router(nodes.router)
app.include_router(library.router)
app.include_router(kpis.router)
app.include_router(sustainability.router)


# Explicit static routes — only these three files are exposed to the browser,
# so the rest of the project root (Python sources, .env, etc.) stays private.
ROOT = Path(__file__).resolve().parent
STATIC_FILES = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/styles.css": ("styles.css", "text/css"),
    "/app.js": ("app.js", "application/javascript"),
}


def _make_static_handler(filename: str, media_type: str):
    def handler():
        path = ROOT / filename
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"{filename} not found")
        return FileResponse(str(path), media_type=media_type)
    return handler


for route, (filename, media_type) in STATIC_FILES.items():
    app.add_api_route(
        route,
        _make_static_handler(filename, media_type),
        methods=["GET"],
        include_in_schema=False,
    )
