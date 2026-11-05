import os
import re
from typing import Annotated, Dict, Any, List, Optional, TypedDict
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from .models import ClusterTopology, ValidationResult
from .tools import (
    plan_cluster_topology,
    validate_topology,
    generate_scripts,
    generate_docker_lab,
    diagnose,
)
from .generator import MQSCGenerator
from .validator import ClusterValidator


class MQAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    intent: str
    cluster_name: Optional[str]
    full_repos: List[str]
    partial_repos: List[str]
    cluster_queues: List[str]
    topology_dict: Optional[Dict[str, Any]]
    validation_dict: Optional[Dict[str, Any]]
    mqsc_scripts: Dict[str, str]
    docker_compose_path: Optional[str]
    diagnostic_results: List[Dict[str, Any]]
    final_response: str


def analyze_intent_node(state: MQAgentState) -> Dict[str, Any]:
    """
    Analyzes the user's message to classify the intent and extract entities
    (cluster name, repository roles, queues, diagnostic codes).
    """
    last_msg = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage) or hasattr(msg, "content"):
            last_msg = str(msg.content)
            break

    text = last_msg.lower()

    # 1. Diagnose intent
    if any(w in text for w in ["amq9", "error", "troubleshoot", "issue", "retrying", "not balancing", "sync"]):
        return {
            "intent": "diagnose",
            "messages": [AIMessage(content="Routing to IBM MQ Cluster Diagnostics engine...")]
        }

    # 2. Generate scripts only
    if ("generate" in text or "mqsc" in text or "scripts" in text) and not any(w in text for w in ["create", "build", "plan"]):
        return {
            "intent": "generate_scripts",
            "messages": [AIMessage(content="Routing to MQSC Script Generator...")]
        }

    # 3. Docker lab only
    if ("docker" in text or "compose" in text or "container" in text) and not any(w in text for w in ["create", "build", "plan"]):
        return {
            "intent": "generate_docker",
            "messages": [AIMessage(content="Routing to Docker Lab Generator...")]
        }

    # 4. Create / Plan cluster intent
    if any(w in text for w in ["create", "plan", "build", "setup", "configure", "cluster"]):
        clus_match = re.search(r"cluster\s+(?:called\s+|named\s+)?['\"]?([A-Za-z0-9._%]+)['\"]?", last_msg, re.IGNORECASE)
        cluster_name = clus_match.group(1).upper() if clus_match else "PROD_CLUS"

        full_repos = []
        partial_repos = []
        cluster_queues = []

        # Parse FR block
        fr_match = re.search(r"(?:fr|full\s*repositor(?:y|ies))\s*[:=]?\s*(.*?)(?=\s+(?:and\s+)?(?:pr|partial|queue)|$)", last_msg, re.IGNORECASE)
        if fr_match:
            for item in re.split(r"[,&]|\band\b", fr_match.group(1)):
                clean = re.sub(r"[^A-Za-z0-9._%]", "", item).upper()
                if clean:
                    full_repos.append(clean)

        # Parse PR block
        pr_match = re.search(r"(?:pr|partial\s*repositor(?:y|ies))\s*[:=]?\s*(.*?)(?=\s+(?:and\s+)?(?:queue|fr)|$)", last_msg, re.IGNORECASE)
        if pr_match:
            for item in re.split(r"[,&]|\band\b", pr_match.group(1)):
                clean = re.sub(r"[^A-Za-z0-9._%]", "", item).upper()
                if clean:
                    partial_repos.append(clean)

        # Parse Queues block
        q_match = re.search(r"(?:queue|queues)\s*[:=]?\s*(.*?)(?=\s+(?:and\s+)?(?:fr|pr)|$)", last_msg, re.IGNORECASE)
        if q_match:
            for item in re.split(r"[,&]|\band\b", q_match.group(1)):
                clean = re.sub(r"[^A-Za-z0-9._%]", "", item).upper()
                if clean:
                    cluster_queues.append(clean)

        if not full_repos:
            full_repos = ["QM1", "QM2"]

        return {
            "intent": "create_cluster",
            "cluster_name": cluster_name,
            "full_repos": full_repos,
            "partial_repos": partial_repos,
            "cluster_queues": cluster_queues,
            "messages": [AIMessage(content=f"Planning cluster '{cluster_name}' with FR: {full_repos}, PR: {partial_repos}...")]
        }

    return {
        "intent": "general",
        "final_response": (
            "I am the IBM MQ Cluster AI Agent built with LangGraph and FastAPI.\n\n"
            "Here is what I can do for you:\n"
            "- **Plan & Create Cluster**: `Create cluster PAYMENT_CLUS with FR QM1, QM2 and PR QM3 and queue ORDERS.IN`\n"
            "- **Validate Topology**: Checks HA repositories, 20-character channel limit, and DEFBIND settings.\n"
            "- **Generate MQSC**: Production-grade scripts for Full and Partial Repositories.\n"
            "- **Generate Docker Lab**: Turnkey multi-node Docker Compose environment.\n"
            "- **Diagnose Cluster Errors**: `Diagnose AMQ9448` or `Diagnose channel retrying`"
        )
    }


def plan_cluster_node(state: MQAgentState) -> Dict[str, Any]:
    """
    Executes the planning tool to construct the ClusterTopology object and auto-wire channels.
    """
    cluster_name = state.get("cluster_name") or "APP_CLUS"
    full_repos = state.get("full_repos") or ["QM1", "QM2"]
    partial_repos = state.get("partial_repos") or []
    cluster_queues = state.get("cluster_queues") or []

    topology = plan_cluster_topology(
        cluster_name=cluster_name,
        full_repositories=full_repos,
        partial_repositories=partial_repos,
        cluster_queues=cluster_queues
    )

    return {
        "topology_dict": topology.model_dump()
    }


def validate_cluster_node(state: MQAgentState) -> Dict[str, Any]:
    """
    Validates the active cluster topology against IBM MQ best practices and RFC/naming constraints.
    """
    top_dict = state.get("topology_dict")
    if not top_dict:
        return {"validation_dict": {"is_valid": False, "errors": ["No topology present."]}}

    topology = ClusterTopology(**top_dict)
    res: ValidationResult = validate_topology(topology)

    return {
        "validation_dict": res.model_dump()
    }


def generate_mqsc_node(state: MQAgentState) -> Dict[str, Any]:
    """
    Generates MQSC scripts for all cluster nodes and writes them to the output directory.
    """
    top_dict = state.get("topology_dict")
    if not top_dict:
        return {"mqsc_scripts": {}}

    topology = ClusterTopology(**top_dict)
    scripts = MQSCGenerator.generate_all_scripts(topology)
    scripts["verify"] = MQSCGenerator.generate_verification_script(topology)

    # Save to disk
    out_dir = Path("output/mqsc")
    generate_scripts(topology, out_dir)

    # Also generate Docker Compose lab
    docker_dir = Path("output/docker")
    compose_path = generate_docker_lab(topology, docker_dir)

    return {
        "mqsc_scripts": scripts,
        "docker_compose_path": str(compose_path)
    }


def diagnose_node(state: MQAgentState) -> Dict[str, Any]:
    """
    Queries the expert diagnostics engine for error resolutions.
    """
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            last_user_msg = str(msg.content)
            break

    if not last_user_msg:
        # Fallback to the first message if no HumanMessage explicitly typed
        msgs = state.get("messages", [])
        if msgs:
            last_user_msg = str(msgs[0].content)

    advices = diagnose(last_user_msg)
    return {
        "diagnostic_results": [a.model_dump() for a in advices]
    }


def synthesize_response_node(state: MQAgentState) -> Dict[str, Any]:
    """
    Synthesizes the final user-facing response from state artifacts.
    """
    intent = state.get("intent", "general")

    if intent == "diagnose":
        advices = state.get("diagnostic_results", [])
        if not advices:
            return {"final_response": "No matching diagnostic rules found for your query. Please provide the exact IBM MQ error code (e.g. AMQ9448, AMQ9202) or symptom."}

        out = ["### 🩺 IBM MQ Cluster Diagnostics\n"]
        for a in advices:
            out.append(f"**Identified Issue**: `{a['code_or_symptom']}` ({a['category']})")
            out.append(f"**Root Cause**: {a['cause']}")
            out.append("**Remediation Steps**:")
            for s in a["remediation_steps"]:
                out.append(f"- {s}")
            if a.get("sample_mqsc"):
                out.append(f"\n```mqsc\n{a['sample_mqsc']}\n```")
            out.append("---")
        return {"final_response": "\n".join(out)}

    if intent == "create_cluster":
        top_dict = state.get("topology_dict", {})
        val_dict = state.get("validation_dict", {})
        scripts = state.get("mqsc_scripts", {})
        docker_path = state.get("docker_compose_path")

        topology = ClusterTopology(**top_dict)
        val = ValidationResult(**val_dict)

        out = [
            f"### 🚀 IBM MQ Cluster Planned: `{topology.cluster_name}`\n",
            f"- **Full Repositories (FR)**: {', '.join(fr.name for fr in topology.full_repositories)}",
            f"- **Partial Repositories (PR)**: {', '.join(pr.name for pr in topology.partial_repositories) or 'None'}",
            f"- **Cluster Queues**: {', '.join(topology.cluster_queues) or 'None'}",
            "\n#### 🔗 Channel Topology & Cross-Connection:",
        ]

        for node in topology.nodes.values():
            sdr_targets = ", ".join(f"TO.{t}" for t in node.cluster_sender_targets) or "None"
            out.append(
                f"- **{node.name}** ({node.role.value}): CLUSRCVR `{node.computed_clusrcvr_name}` on `{node.conname}` | CLUSSDR -> `{sdr_targets}`"
            )

        out.append("\n#### 🛡️ Validation & Architectural Health:")
        if val.is_valid:
            out.append("✅ **Topology is valid and conforms to IBM MQ High-Availability standards.**")
        else:
            out.append("❌ **Validation Errors:**")
            for err in val.errors:
                out.append(f"  - {err}")

        for w in val.warnings:
            out.append(f"⚠️ **Warning**: {w}")

        for r in val.recommendations:
            out.append(f"💡 **Recommendation**: {r}")

        out.append("\n#### 📄 Generated Artifacts:")
        out.append(f"- **MQSC Scripts**: Generated for {', '.join(scripts.keys())} in `output/mqsc/`")
        if docker_path:
            out.append(f"- **Docker Compose Lab**: Ready at `{docker_path}`")
            out.append("\nTo start your local cluster testbed:")
            out.append("```bash\ncd output/docker && docker compose up -d\n```")

        return {"final_response": "\n".join(out)}

    if intent in ["generate_scripts", "generate_docker"]:
        scripts = state.get("mqsc_scripts", {})
        docker_path = state.get("docker_compose_path")
        return {
            "final_response": f"Generated MQSC scripts for: {', '.join(scripts.keys())}.\nDocker compose lab generated at: `{docker_path}`."
        }

    return {"final_response": state.get("final_response", "Operation completed.")}


def route_intent(state: MQAgentState) -> str:
    """
    Router determining the next node based on classified intent.
    """
    intent = state.get("intent", "general")
    if intent == "create_cluster":
        return "plan_cluster"
    elif intent == "diagnose":
        return "diagnose"
    elif intent in ["generate_scripts", "generate_docker"]:
        return "plan_cluster"
    else:
        return "respond"


# Build the LangGraph StateGraph
def build_cluster_agent_graph():
    builder = StateGraph(MQAgentState)

    builder.add_node("analyze_intent", analyze_intent_node)
    builder.add_node("plan_cluster", plan_cluster_node)
    builder.add_node("validate_cluster", validate_cluster_node)
    builder.add_node("generate_mqsc", generate_mqsc_node)
    builder.add_node("diagnose", diagnose_node)
    builder.add_node("respond", synthesize_response_node)

    # Edge from START to analyze_intent
    builder.add_edge(START, "analyze_intent")

    # Conditional router from analyze_intent
    builder.add_conditional_edges(
        "analyze_intent",
        route_intent,
        {
            "plan_cluster": "plan_cluster",
            "diagnose": "diagnose",
            "respond": "respond"
        }
    )

    # Creation pipeline
    builder.add_edge("plan_cluster", "validate_cluster")
    builder.add_edge("validate_cluster", "generate_mqsc")
    builder.add_edge("generate_mqsc", "respond")

    # Diagnostic pipeline
    builder.add_edge("diagnose", "respond")

    # Edge from respond to END
    builder.add_edge("respond", END)

    return builder.compile()


# Singleton instance
langgraph_agent_app = build_cluster_agent_graph()
