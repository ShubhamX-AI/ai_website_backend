import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src.api.routes import token, health
from src.core.logger import setup_logging

# Setup logging
setup_logging()

app = FastAPI(title="LiveKit AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(token.router, prefix="/api")
app.include_router(health.router)

# Serve built MkDocs static site at /documentation (run `mkdocs build` first)
_DOCS_SITE = os.path.join(os.path.dirname(__file__), "..", "..", "site")
if os.path.isdir(_DOCS_SITE):
    app.mount("/documentation", StaticFiles(directory=_DOCS_SITE, html=True), name="documentation")

if __name__ == "__main__":
    import uvicorn
    from src.core.config import settings
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
