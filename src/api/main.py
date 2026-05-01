import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src.api.routes import token, health, auth
from src.core.database import init_db
from src.core.logger import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="LiveKit AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(token.router, prefix="/api")
app.include_router(health.router)
app.include_router(auth.router)

# Serve built MkDocs static site at /documentation (run `mkdocs build` first)
_DOCS_SITE = os.path.join(os.path.dirname(__file__), "..", "..", "site")
if os.path.isdir(_DOCS_SITE):
    app.mount("/documentation", StaticFiles(directory=_DOCS_SITE, html=True), name="documentation")

if __name__ == "__main__":
    import uvicorn
    from src.core.config import settings
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
