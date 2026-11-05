from pathlib import Path
from typing import List, Dict, Optional, Any
from .models import (
    ClusterTopology,
    QMgrNode,
    QMgrRole,
    ValidationResult,
    ExecutionMode
)
from .validator import ClusterValidator
from .generator import MQSCGenerator
from .executors import (
    MockExecutor,
    CLIExecutor,
    RESTExecutor,
    DockerOrchestrator,
    ExecutionResult
)
from .diagnostics import ClusterDiagnostics, DiagnosticAdvice


def plan_cluster_topology(
    cluster_name: str,
    full_repositories: List[str],
    partial_repositories: Optional[List[str]] = None,
    host: str = "localhost",
    base_port: int = 1414,
    base_rest_port: int = 9443,
    cluster_queues: Optional[List[str]] = None
) -> ClusterTopology:
    """
    Plans and builds an IBM MQ ClusterTopology with auto-allocated ports
    and auto-wired CLUSSDR / CLUSRCVR channels.
    """
    partial_repositories = partial_repositories or []
    cluster_queues = cluster_queues or []

    topology = ClusterTopology(
        cluster_name=cluster_name.strip().upper(),
        description=f"Automated IBM MQ Cluster: {cluster_name.strip().upper()}",
        cluster_queues=[q.strip().upper() for q in cluster_queues]
    )

    port_offset = 0

    # Add Full Repositories
    for fr_name in full_repositories:
        clean_name = fr_name.strip().upper()
        node = QMgrNode(
            name=clean_name,
            role=QMgrRole.FULL_REPOSITORY,
            host=host,
            port=base_port + port_offset,
            rest_port=base_rest_port + port_offset,
            description=f"Full Repository node {clean_name}"
        )
        topology.nodes[clean_name] = node
        port_offset += 1

    # Add Partial Repositories
    for pr_name in partial_repositories:
        clean_name = pr_name.strip().upper()
        node = QMgrNode(
            name=clean_name,
            role=QMgrRole.PARTIAL_REPOSITORY,
            host=host,
            port=base_port + port_offset,
            rest_port=base_rest_port + port_offset,
            description=f"Partial Repository node {clean_name}"
        )
        topology.nodes[clean_name] = node
        port_offset += 1

    # Wire CLUSSDR channels based on IBM best practice
    MQSCGenerator.auto_wire_topology(topology)

    return topology


def validate_topology(topology: ClusterTopology) -> ValidationResult:
    """
    Runs the full IBM MQ cluster validation rules against the topology.
    """
    return ClusterValidator.validate(topology)


def generate_scripts(topology: ClusterTopology, output_dir: Path) -> Dict[str, Path]:
    """
    Writes verified MQSC script files to output_dir.
    """
    return MQSCGenerator.write_scripts_to_disk(topology, output_dir)


def generate_docker_lab(topology: ClusterTopology, output_dir: Path) -> Path:
    """
    Generates a local multi-node Docker Compose lab for testing the cluster.
    """
    return DockerOrchestrator.generate_docker_lab(topology, output_dir)


def execute_cluster(
    topology: ClusterTopology,
    mode: ExecutionMode = ExecutionMode.SIMULATION,
    rest_url: Optional[str] = None,
    username: str = "admin",
    password: str = "pass"
) -> Dict[str, ExecutionResult]:
    """
    Executes the cluster configuration against the selected backend.
    """
    scripts = MQSCGenerator.generate_all_scripts(topology)
    results: Dict[str, ExecutionResult] = {}

    if mode == ExecutionMode.SIMULATION:
        executor = MockExecutor()
    elif mode == ExecutionMode.LOCAL_RUNMQSC:
        executor = CLIExecutor()
    elif mode == ExecutionMode.REST_API:
        executor = RESTExecutor(
            base_url=rest_url or f"https://{list(topology.nodes.values())[0].host}:{list(topology.nodes.values())[0].rest_port}",
            username=username,
            password=password
        )
    else:
        raise ValueError(f"Unsupported execution mode: {mode}")

    for qm_name, script_content in scripts.items():
        res = executor.execute_mqsc(qm_name, script_content)
        results[qm_name] = res

    return results


def diagnose(query: str) -> List[DiagnosticAdvice]:
    """
    Looks up diagnostics and troubleshooting recommendations for MQ cluster errors.
    """
    return ClusterDiagnostics.diagnose(query)
