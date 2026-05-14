from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routers import documents, nodes

app = FastAPI(
    title="Business Process Repository",
    description="Phase 1 of The Kendall Group Business Operating System (BOS).",
    version="0.1.0",
)

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
app.include_router(documents.router)


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
