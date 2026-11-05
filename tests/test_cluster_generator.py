import pytest
from pathlib import Path
from mq_agent.models import ClusterTopology, QMgrRole
from mq_agent.tools import (
    plan_cluster_topology,
    validate_topology,
    generate_scripts,
    generate_docker_lab,
    diagnose,
)
from mq_agent.generator import MQSCGenerator
from mq_agent.validator import ClusterValidator


def test_topology_creation_and_autowire():
    topology = plan_cluster_topology(
        cluster_name="PAYMENT_CLUS",
        full_repositories=["QM1", "QM2"],
        partial_repositories=["QM3"],
        cluster_queues=["PAYMENT.REQUESTS"]
    )

    assert topology.cluster_name == "PAYMENT_CLUS"
    assert len(topology.nodes) == 3
    assert len(topology.full_repositories) == 2
    assert len(topology.partial_repositories) == 1

    # Check ports auto-incremented
    assert topology.nodes["QM1"].port == 1414
    assert topology.nodes["QM2"].port == 1415
    assert topology.nodes["QM3"].port == 1416

    # Check auto-wiring
    # QM1 should point to QM2
    assert "QM2" in topology.nodes["QM1"].cluster_sender_targets
    # QM2 should point to QM1
    assert "QM1" in topology.nodes["QM2"].cluster_sender_targets
    # QM3 should point to both QM1 and QM2
    assert "QM1" in topology.nodes["QM3"].cluster_sender_targets
    assert "QM2" in topology.nodes["QM3"].cluster_sender_targets


def test_validator_ha_warning():
    # Only 1 FR should produce a warning
    topology = plan_cluster_topology(
        cluster_name="SINGLE_FR_CLUS",
        full_repositories=["QM1"],
        partial_repositories=["QM2"]
    )
    res = validate_topology(topology)
    assert res.is_valid  # Still strictly valid syntax
    assert any("IBM strongly recommends exactly 2 Full Repositories" in w for w in res.warnings)


def test_validator_channel_name_limit():
    # Channel name length > 20 characters should fail
    # TO.VERY_LONG_QUEUE_MGR_NAME is 27 chars!
    topology = plan_cluster_topology(
        cluster_name="CLUS",
        full_repositories=["VERY_LONG_QUEUE_MGR_NAME"]
    )
    res = validate_topology(topology)
    assert not res.is_valid
    assert any("exceeds 20 characters" in err for err in res.errors)


def test_mqsc_script_generation(tmp_path: Path):
    topology = plan_cluster_topology(
        cluster_name="ORDER_CLUS",
        full_repositories=["FR1", "FR2"],
        partial_repositories=["PR1"],
        cluster_queues=["ORDER.QUEUE"]
    )

    scripts = MQSCGenerator.generate_all_scripts(topology)

    # Check Full Repository FR1
    fr1_mqsc = scripts["FR1"]
    assert "ALTER QMGR REPOS('ORDER_CLUS')" in fr1_mqsc
    assert "DEFINE CHANNEL('TO.FR1') +" in fr1_mqsc
    assert "CHLTYPE(CLUSRCVR)" in fr1_mqsc
    assert "DEFINE CHANNEL('TO.FR2') +" in fr1_mqsc
    assert "CHLTYPE(CLUSSDR)" in fr1_mqsc
    assert "DEFBIND(NOTFIXED)" in fr1_mqsc

    # Check Partial Repository PR1
    pr1_mqsc = scripts["PR1"]
    assert "ALTER QMGR REPOS" not in pr1_mqsc
    assert "DEFINE CHANNEL('TO.PR1') +" in pr1_mqsc
    assert "DEFINE CHANNEL('TO.FR1') +" in pr1_mqsc

    # Check writing to disk
    files = generate_scripts(topology, tmp_path)
    assert (tmp_path / "FR1.mqsc").exists()
    assert (tmp_path / "FR2.mqsc").exists()
    assert (tmp_path / "PR1.mqsc").exists()
    assert (tmp_path / "ORDER_CLUS_verify.mqsc").exists()


def test_docker_lab_generation(tmp_path: Path):
    topology = plan_cluster_topology(
        cluster_name="LAB_CLUS",
        full_repositories=["QM1", "QM2"],
        partial_repositories=["QM3"]
    )
    compose_file = generate_docker_lab(topology, tmp_path)
    assert compose_file.exists()
    content = compose_file.read_text(encoding="utf-8")
    assert "qm1" in content
    assert "qm2" in content
    assert "qm3" in content
    assert "mq-cluster-net" in content


def test_diagnostics():
    advices = diagnose("AMQ9448")
    assert len(advices) >= 1
    assert advices[0].code_or_symptom == "AMQ9448"

    retrying = diagnose("channel is in retrying status")
    assert len(retrying) >= 1
    assert "CHANNEL_RETRYING" in retrying[0].code_or_symptom
