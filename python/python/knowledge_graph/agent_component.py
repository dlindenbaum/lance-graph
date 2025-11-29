"""FastAPI component for the Graph Review Agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from .agent import IntegratedCDRAgent, ChatRequest, ChatResponse
from .config import KnowledgeGraphConfig
from .service import LanceKnowledgeGraph
from .store import LanceGraphStore


class GraphReviewAgentComponent:
    """FastAPI routes for the graph review agent."""

    def __init__(
        self,
        config: Optional[KnowledgeGraphConfig] = None,
        duckdb_path: Optional[str] = None,
    ):
        self._config = config or KnowledgeGraphConfig.default()
        self._duckdb_path = duckdb_path
        self._service: Optional[LanceKnowledgeGraph] = None
        self._agent: Optional[IntegratedCDRAgent] = None
        self.router = APIRouter(tags=["graph-review-agent"])
        self._setup_routes()

    def _get_service(self) -> LanceKnowledgeGraph:
        """Get or create the knowledge graph service."""
        if self._service is None:
            try:
                graph_config = self._config.load_graph_config()
                storage = LanceGraphStore(self._config)
                self._service = LanceKnowledgeGraph(graph_config, storage=storage)
                self._service.ensure_initialized()
            except FileNotFoundError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
        return self._service

    def _get_agent(self) -> IntegratedCDRAgent:
        """Get or create the integrated CDR investigation agent."""
        if self._agent is None:
            from .agent import AgentConfig

            service = self._get_service()
            # Agent config is loaded from environment variables
            agent_config = AgentConfig.from_env()
            self._agent = IntegratedCDRAgent(
                service=service,
                config=agent_config,
                duckdb_path=self._duckdb_path,
            )
        return self._agent

    def _setup_routes(self) -> None:
        @self.router.post("/agent/chat", response_model=ChatResponse)
        async def chat_with_agent(request: ChatRequest) -> ChatResponse:
            """Send a message to the agent and get a response."""
            agent = self._get_agent()
            try:
                response = await agent.process_message(
                    request.message, case_id=request.case_id
                )
                return response
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Agent error: {str(e)}"
                ) from e

        @self.router.post("/agent/reset")
        async def reset_agent() -> Dict[str, str]:
            """Reset the agent conversation history."""
            agent = self._get_agent()
            agent.reset_conversation()
            return {"status": "ok", "message": "Agent conversation reset"}

        @self.router.get("/agent/status")
        async def get_agent_status() -> Dict[str, Any]:
            """Get the current agent status."""
            agent = self._get_agent()
            stats = agent.get_router_stats()
            return {
                "status": "ready",
                "iteration_count": agent.iteration_count,
                "conversation_length": len(agent.conversation_history),
                **stats,
                "config": {
                    "temperature": agent.config.temperature,
                    "max_tokens": agent.config.max_tokens,
                    "routing_strategy": agent.config.router.routing_strategy,
                },
            }

        @self.router.get("/agent/artifacts/{artifact_id}")
        async def get_artifact(artifact_id: str) -> Dict[str, Any]:
            """Retrieve artifact data by ID.

            Args:
                artifact_id: The artifact identifier

            Returns:
                Full artifact data including all properties

            Raises:
                404: If artifact not found or expired
            """
            from .agent import get_artifact_store

            store = get_artifact_store()
            data = store.retrieve(artifact_id)

            if not data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Artifact {artifact_id} not found or expired"
                )

            return data

        @self.router.websocket("/agent/ws")
        async def websocket_agent(websocket: WebSocket):
            """WebSocket endpoint for real-time agent communication."""
            await websocket.accept()
            agent = self._get_agent()

            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_json()
                    message = data.get("message", "")

                    if not message:
                        await websocket.send_json(
                            {"error": "Message cannot be empty"}
                        )
                        continue

                    # Process with agent
                    response = await agent.process_message(message)

                    # Send response
                    await websocket.send_json(response.model_dump(mode="json"))

            except WebSocketDisconnect:
                pass
            except Exception as e:
                await websocket.send_json({"error": str(e)})
                await websocket.close()

    def close(self) -> None:
        """Release retained resources."""
        if self._agent:
            self._agent.close()
        self._service = None
        self._agent = None
