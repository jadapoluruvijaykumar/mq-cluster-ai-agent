from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage
from mq_agent.langgraph_agent import langgraph_agent_app
from mq_agent.models import ClusterTopology, ValidationResult
from mq_agent.tools import (
    plan_cluster_topology,
    validate_topology,
    generate_scripts,
    generate_docker_lab,
    diagnose,
)
from mq_agent.generator import MQSCGenerator
from config import OUTPUT_DIR, MQSC_OUTPUT_DIR, DOCKER_OUTPUT_DIR

app = FastAPI(
    title="IBM MQ Cluster AI Agent API",
    description="FastAPI + LangGraph backend for planning, validating, generating, and troubleshooting IBM MQ Clusters.",
    version="1.0.0"
)

# Enable CORS for local/dev use
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for currently active topology
active_topology: Optional[ClusterTopology] = None


class ChatRequest(BaseModel):
    message: str = Field(..., json_schema_extra={"example": "Create cluster PAYMENT_CLUS with FR QM1, QM2 and PR QM3 and queue ORDERS.IN"})


class PlanClusterRequest(BaseModel):
    cluster_name: str = Field(..., json_schema_extra={"example": "PAYMENT_CLUS"})
    full_repositories: List[str] = Field(..., json_schema_extra={"example": ["QM1", "QM2"]})
    partial_repositories: List[str] = Field(default_factory=list, json_schema_extra={"example": ["QM3"]})
    cluster_queues: List[str] = Field(default_factory=list, json_schema_extra={"example": ["PAYMENT.REQ"]})
    host: str = Field("localhost")
    base_port: int = Field(1414)


@app.get("/", response_class=FileResponse)
def get_web_ui():
    """Serves the interactive web interface."""
    index_file = Path("web/index.html")
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Web UI not found.")
    return FileResponse(index_file)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "agent": "LangGraph + FastAPI IBM MQ Agent",
        "active_cluster": active_topology.cluster_name if active_topology else None
    }


@app.post("/api/chat")
def chat_with_agent(req: ChatRequest):
    """
    Submits a message to the LangGraph Cluster Agent.
    Executes the StateGraph: intent_analyzer -> planner -> validator -> generator -> responder.
    """
    global active_topology

    state_input = {
        "messages": [HumanMessage(content=req.message)]
    }

    result = langgraph_agent_app.invoke(state_input)

    # If a topology was constructed, store it in memory
    top_dict = result.get("topology_dict")
    if top_dict:
        active_topology = ClusterTopology(**top_dict)

    return {
        "response": result.get("final_response", ""),
        "intent": result.get("intent", ""),
        "topology": top_dict,
        "validation": result.get("validation_dict"),
        "scripts": result.get("mqsc_scripts", {}),
        "docker_path": result.get("docker_compose_path")
    }


@app.post("/api/cluster/plan")
def plan_cluster(req: PlanClusterRequest):
    """
    Direct endpoint to plan a cluster topology and validate it.
    """
    global active_topology
    topology = plan_cluster_topology(
        cluster_name=req.cluster_name,
        full_repositories=req.full_repositories,
        partial_repositories=req.partial_repositories,
        host=req.host,
        base_port=req.base_port,
        cluster_queues=req.cluster_queues
    )
    active_topology = topology
    validation = validate_topology(topology)

    return {
        "topology": topology.model_dump(),
        "validation": validation.model_dump()
    }


@app.get("/api/cluster/active")
def get_active_cluster():
    """
    Returns the currently active cluster topology and validation results.
    """
    if not active_topology:
        raise HTTPException(status_code=404, detail="No cluster topology currently active.")
    validation = validate_topology(active_topology)
    return {
        "topology": active_topology.model_dump(),
        "validation": validation.model_dump()
    }


@app.post("/api/cluster/generate")
def generate_mqsc():
    """
    Generates MQSC scripts for the active cluster and saves them to disk.
    """
    if not active_topology:
        raise HTTPException(status_code=400, detail="No cluster active. Please plan a cluster first.")

    scripts = MQSCGenerator.generate_all_scripts(active_topology)
    scripts["verify"] = MQSCGenerator.generate_verification_script(active_topology)
    written = generate_scripts(active_topology, MQSC_OUTPUT_DIR)

    return {
        "scripts": scripts,
        "files": {k: str(v.resolve()) for k, v in written.items()}
    }


@app.get("/api/cluster/docker-preview", response_class=PlainTextResponse)
def get_docker_compose_preview():
    """
    Returns the generated docker-compose.yml file content.
    """
    compose_path = DOCKER_OUTPUT_DIR / "docker-compose.yml"
    if not compose_path.exists():
        if active_topology:
            generate_docker_lab(active_topology, DOCKER_OUTPUT_DIR)
        else:
            return "# No active cluster to generate docker-compose.yml"
    return compose_path.read_text(encoding="utf-8")


@app.get("/api/cluster/diagnose")
def diagnose_error(query: str = Query(..., examples=["AMQ9448"])):
    """
    Diagnoses cluster errors, channel issues, or symptoms.
    """
    advices = diagnose(query)
    return {"matches": [a.model_dump() for a in advices]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
