"""FastAPI main application for Incident Brain.
Exposes REST endpoints for investigation, graph exploration, incident logging,
demo reset, and serves the dark glassmorphic web UI.
"""

from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import os
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.db import db_manager
from app.seed import seed_database
from app.agent import brain_agent
from app.tools import log_incident

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("incident_brain.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure initial graph seed exists
    logger.info("Initializing Incident Brain...")
    seed_database(reset=False)
    yield
    logger.info("Shutting down Incident Brain.")


app = FastAPI(
    title="Incident Brain API",
    description="FalkorDB Graph-Powered Autonomous Incident Copilot",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static folder
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class InvestigateRequest(BaseModel):
    service: str = Field(..., json_schema_extra={"example": "auth-service"})
    symptoms: Optional[str] = Field(default="", json_schema_extra={"example": "504 Gateway Timeout and connection leaks"})
    team: Optional[str] = Field(default="core_platform", json_schema_extra={"example": "core_platform"})


class LogIncidentRequest(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "Auth Service HikariCP Leak in Token Validation"})
    service: str = Field(..., json_schema_extra={"example": "auth-service"})
    root_cause: str = Field(..., json_schema_extra={"example": "Unclosed session handle during signature validation"})
    fix: str = Field(..., json_schema_extra={"example": "Added try-finally session close and bumped pool to 60"})
    team: Optional[str] = Field(default="core_platform", json_schema_extra={"example": "core_platform"})
    severity: Optional[str] = Field(default="P1", json_schema_extra={"example": "P1"})


@app.get("/health")
def health_check():
    """Health status including native FalkorDB connectivity and active agent mode."""
    return {
        "status": "healthy",
        "falkordb_connected": db_manager.is_connected,
        "database_backend": "FalkorDB Native (Redis Protocol)" if db_manager.is_connected else "FalkorDB GraphBLAS Simulator (In-Memory)",
        "agent_mode": brain_agent.active_mode,
        "company_graph": settings.COMPANY_GRAPH
    }


@app.get("/")
def serve_index():
    """Serves the interactive single-page dashboard."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Incident Brain API is running. UI template pending creation."}, status_code=200)


@app.post("/api/investigate")
def run_investigation(req: InvestigateRequest):
    """Executes multi-agent graph investigation with blast radius, risk ranking, and postmortem."""
    try:
        result = brain_agent.investigate(
            service=req.service,
            symptoms=req.symptoms or "",
            team=req.team or "core_platform"
        )
        return result
    except Exception as e:
        logger.error(f"Investigation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/incidents")
def create_incident(req: LogIncidentRequest):
    """Logs a new incident into the team's isolated memory graph and links to company graph."""
    try:
        res = log_incident(
            title=req.title,
            service=req.service,
            root_cause=req.root_cause,
            fix=req.fix,
            team=req.team or "core_platform",
            severity=req.severity or "P1"
        )
        return res
    except Exception as e:
        logger.error(f"Error logging incident: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph")
def get_graph(graph: Optional[str] = Query(default=None)):
    """Returns the visual graph nodes and relationships for the force-graph canvas."""
    target_graph = graph or settings.COMPANY_GRAPH
    snapshot = db_manager.get_snapshot(target_graph)
    return snapshot


@app.get("/api/memory")
def get_team_memory(team: str = Query(default="core_platform")):
    """Returns the isolated team memory graph (Track 2: Agent memory across sessions)."""
    mem_graph = f"memory_{team}"
    snapshot = db_manager.get_snapshot(mem_graph)
    return {
        "team": team,
        "graph_name": mem_graph,
        "snapshot": snapshot
    }


@app.post("/api/reset-demo")
def reset_demo():
    """Resets and re-seeds graphs for reliable demo reproducibility."""
    seed_database(reset=True)
    snapshot = db_manager.get_snapshot(settings.COMPANY_GRAPH)
    return {
        "status": "reset_complete",
        "nodes": len(snapshot.get("nodes", [])),
        "links": len(snapshot.get("links", []))
    }
