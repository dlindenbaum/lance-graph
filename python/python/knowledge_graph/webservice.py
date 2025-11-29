"""Standalone FastAPI application for the Lance knowledge graph."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent_component import GraphReviewAgentComponent
from .component import KnowledgeGraphComponent

if TYPE_CHECKING:
    from .config import KnowledgeGraphConfig


def create_app(config: Optional["KnowledgeGraphConfig"] = None) -> FastAPI:
    component = KnowledgeGraphComponent(config)
    agent_component = GraphReviewAgentComponent(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            component.close()
            agent_component.close()

    app = FastAPI(
        title="Lance Knowledge Graph API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(component.router, prefix="/graph")
    app.include_router(agent_component.router, prefix="/api")
    return app


app = create_app()


def main() -> None:
    """Run the web service using uvicorn."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
