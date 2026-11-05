import re
from typing import Dict, Tuple, Set
from .models import ClusterTopology, ValidationResult, QMgrRole


class ClusterValidator:
    """
    Validates IBM MQ Cluster topology against IBM best practices,
    naming constraints, and network routing rules.
    """

    MQ_OBJECT_NAME_REGEX = re.compile(r"^[A-Z0-9._%]+$")

    @classmethod
    def validate(cls, topology: ClusterTopology) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        cls._validate_cluster_name(topology, result)
        cls._validate_repositories(topology, result)
        cls._validate_nodes_and_ports(topology, result)
        cls._validate_channel_names(topology, result)
        cls._validate_connectivity(topology, result)
        cls._validate_cluster_queues(topology, result)

        if result.errors:
            result.is_valid = False

        return result

    @classmethod
    def _validate_cluster_name(cls, topology: ClusterTopology, result: ValidationResult):
        name = topology.cluster_name
        if len(name) > 48:
            result.errors.append(f"Cluster name '{name}' exceeds maximum length of 48 characters ({len(name)} chars).")
        if not cls.MQ_OBJECT_NAME_REGEX.match(name):
            result.warnings.append(
                f"Cluster name '{name}' contains special characters that may require escaping in MQSC."
            )

    @classmethod
    def _validate_repositories(cls, topology: ClusterTopology, result: ValidationResult):
        fr_list = topology.full_repositories
        pr_list = topology.partial_repositories
        total_nodes = len(topology.nodes)

        if total_nodes == 0:
            result.errors.append("Topology contains no Queue Managers.")
            return

        if len(fr_list) == 0:
            result.errors.append(
                "A cluster requires at least one Full Repository (FR) to operate. No FRs are defined."
            )
        elif len(fr_list) == 1 and total_nodes > 1:
            result.warnings.append(
                f"Only 1 Full Repository ('{fr_list[0].name}') is defined. "
                "IBM strongly recommends exactly 2 Full Repositories for High Availability (HA) to eliminate single points of failure."
            )
            result.recommendations.append(
                "Designate a second Queue Manager as a Full Repository (FR) to ensure cluster resiliency if one repository goes down."
            )
        elif len(fr_list) > 2:
            result.warnings.append(
                f"Cluster defines {len(fr_list)} Full Repositories. "
                "IBM best practice recommends exactly 2 Full Repositories to prevent excessive cluster gossip and repository update traffic."
            )

    @classmethod
    def _validate_nodes_and_ports(cls, topology: ClusterTopology, result: ValidationResult):
        endpoints: Dict[Tuple[str, int], str] = {}

        for qm_name, node in topology.nodes.items():
            if len(qm_name) > 48:
                result.errors.append(f"Queue Manager name '{qm_name}' exceeds 48 characters.")

            # Validate port numbers
            if not (1 <= node.port <= 65535):
                result.errors.append(f"Queue Manager '{qm_name}' port {node.port} is out of valid range (1-65535).")

            # Check port conflicts
            endpoint_key = (node.host.lower(), node.port)
            if endpoint_key in endpoints:
                result.errors.append(
                    f"Port conflict detected! Queue Managers '{endpoints[endpoint_key]}' and '{qm_name}' "
                    f"both bind to {node.host}:{node.port}."
                )
            else:
                endpoints[endpoint_key] = qm_name

    @classmethod
    def _validate_channel_names(cls, topology: ClusterTopology, result: ValidationResult):
        for qm_name, node in topology.nodes.items():
            clusrcvr = node.computed_clusrcvr_name
            # IBM MQ channel name limit is strictly 20 characters!
            if len(clusrcvr) > 20:
                result.errors.append(
                    f"Cluster-Receiver channel name '{clusrcvr}' for QMgr '{qm_name}' exceeds 20 characters ({len(clusrcvr)} chars). "
                    f"Please shorten the QMgr name or provide an explicit clusrcvr_channel_name."
                )

            # Check target channel names for CLUSSDR
            for target_name in node.cluster_sender_targets:
                target_node = topology.nodes.get(target_name)
                target_clusrcvr = target_node.computed_clusrcvr_name if target_node else f"TO.{target_name}"
                if len(target_clusrcvr) > 20:
                    result.errors.append(
                        f"Cluster-Sender channel '{target_clusrcvr}' from '{qm_name}' to '{target_name}' exceeds 20 characters."
                    )

    @classmethod
    def _validate_connectivity(cls, topology: ClusterTopology, result: ValidationResult):
        fr_names = {fr.name for fr in topology.full_repositories}

        # Check that Full Repositories point to each other
        if len(fr_names) >= 2:
            for fr in topology.full_repositories:
                other_frs = fr_names - {fr.name}
                connected_frs = set(fr.cluster_sender_targets).intersection(other_frs)
                if not connected_frs:
                    result.warnings.append(
                        f"Full Repository '{fr.name}' has no CLUSSDR configured to any other Full Repository. "
                        f"In an HA cluster, Full Repositories should have cluster sender channels to each other."
                    )

        # Check Partial Repositories point to at least one FR
        for pr in topology.partial_repositories:
            connected_frs = set(pr.cluster_sender_targets).intersection(fr_names)
            if not connected_frs and fr_names:
                result.errors.append(
                    f"Partial Repository '{pr.name}' does not have a CLUSSDR channel pointing to any Full Repository."
                )

    @classmethod
    def _validate_cluster_queues(cls, topology: ClusterTopology, result: ValidationResult):
        for q_name in topology.cluster_queues:
            if len(q_name) > 48:
                result.errors.append(f"Cluster Queue name '{q_name}' exceeds maximum length of 48 characters.")
            if not cls.MQ_OBJECT_NAME_REGEX.match(q_name.upper()):
                result.warnings.append(
                    f"Cluster Queue name '{q_name}' contains characters that might require escaping in MQSC."
                )
        if topology.cluster_queues:
            result.recommendations.append(
                "Cluster queues will be defined with DEFBIND(NOTFIXED) to ensure message-by-message workload balancing."
            )
