from api import (
    health_check,
    chat_with_agent,
    plan_cluster,
    diagnose_error,
    ChatRequest,
    PlanClusterRequest
)
from mq_agent.langgraph_agent import langgraph_agent_app
from langchain_core.messages import HumanMessage


def test_api_health():
    data = health_check()
    assert data["status"] == "healthy"
    assert "LangGraph" in data["agent"]


def test_langgraph_agent_chat_api():
    req = ChatRequest(
        message="Create cluster INVOICE_CLUS with FR QM1, QM2 and PR QM3 and queue INVOICES.IN"
    )
    data = chat_with_agent(req)

    assert data["intent"] == "create_cluster"
    assert "INVOICE_CLUS" in data["response"]
    assert data["topology"] is not None
    assert data["topology"]["cluster_name"] == "INVOICE_CLUS"
    assert len(data["topology"]["nodes"]) == 3
    assert "QM1" in data["scripts"]
    assert "QM2" in data["scripts"]
    assert "QM3" in data["scripts"]


def test_api_plan_cluster():
    req = PlanClusterRequest(
        cluster_name="API_TEST_CLUS",
        full_repositories=["QM_A", "QM_B"],
        partial_repositories=["QM_C"],
        cluster_queues=["API.QUEUE"]
    )
    data = plan_cluster(req)

    assert data["topology"]["cluster_name"] == "API_TEST_CLUS"
    assert data["validation"]["is_valid"] is True


def test_api_diagnose():
    data = diagnose_error(query="AMQ9448")
    assert len(data["matches"]) >= 1
    assert data["matches"][0]["code_or_symptom"] == "AMQ9448"


def test_langgraph_direct_diagnose():
    state = {
        "messages": [HumanMessage(content="diagnose channel retrying issue")]
    }
    result = langgraph_agent_app.invoke(state)
    assert result["intent"] == "diagnose"
    assert "CHANNEL_RETRYING" in result["final_response"] or "remediation" in result["final_response"].lower()
