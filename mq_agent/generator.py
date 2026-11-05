from typing import Dict, List, Optional
from pathlib import Path
from .models import ClusterTopology, QMgrNode, QMgrRole


class MQSCGenerator:
    """
    Generates industry-standard MQSC scripts for IBM MQ Cluster deployment,
    verification, and teardown.
    """

    @classmethod
    def auto_wire_topology(cls, topology: ClusterTopology) -> ClusterTopology:
        """
        Automatically wires CLUSSDR targets based on best-practice IBM MQ topology rules:
        - Full Repositories point to other Full Repositories.
        - Partial Repositories point to all Full Repositories.
        """
        fr_nodes = topology.full_repositories
        fr_names = [fr.name for fr in fr_nodes]

        for qm_name, node in topology.nodes.items():
            if not node.cluster_sender_targets:
                if node.role == QMgrRole.FULL_REPOSITORY:
                    # Point to other FRs
                    node.cluster_sender_targets = [name for name in fr_names if name != qm_name]
                else:
                    # Partial repo points to available FRs
                    node.cluster_sender_targets = list(fr_names)

        return topology

    @classmethod
    def generate_qmgr_script(cls, topology: ClusterTopology, qm_name: str) -> str:
        """
        Generates the MQSC definition script for a single Queue Manager in the cluster.
        """
        node = topology.nodes.get(qm_name)
        if not node:
            raise ValueError(f"Queue Manager '{qm_name}' not found in topology.")

        cluster_name = topology.cluster_name
        lines: List[str] = [
            f"* ==================================================================",
            f"* IBM MQ Cluster Setup Script for Queue Manager: {node.name}",
            f"* Role: {'FULL REPOSITORY (FR)' if node.role == QMgrRole.FULL_REPOSITORY else 'PARTIAL REPOSITORY (PR)'}",
            f"* Target Cluster: {cluster_name}",
            f"* ==================================================================",
            "",
            "* 1. Configure TCP Listener",
            f"DEFINE LISTENER('{node.computed_listener_name}') TRPTYPE(TCP) PORT({node.port}) CONTROL(QMGR) REPLACE",
            f"START LISTENER('{node.computed_listener_name}')",
            "",
        ]

        # 2. Configure Full Repository if applicable
        if node.role == QMgrRole.FULL_REPOSITORY:
            lines.extend([
                "* 2. Designate this Queue Manager as a Full Repository",
                f"ALTER QMGR REPOS('{cluster_name}')",
                "",
            ])
        else:
            lines.extend([
                "* 2. Partial Repository: No REPOS attribute needed",
                "* (Cluster state is requested on-demand from Full Repositories)",
                "",
            ])

        # 3. Cluster-Receiver Channel (CLUSRCVR)
        # Defined so other queue managers can connect to this queue manager
        clusrcvr_name = node.computed_clusrcvr_name
        lines.extend([
            "* 3. Cluster-Receiver Channel (CLUSRCVR)",
            f"* Allows all cluster members to send cluster information and messages to {node.name}",
            f"DEFINE CHANNEL('{clusrcvr_name}') +",
            f"       CHLTYPE(CLUSRCVR) +",
            f"       TRPTYPE(TCP) +",
            f"       CONNAME('{node.conname}') +",
            f"       CLUSTER('{cluster_name}') +",
            f"       DESCR('Cluster receiver channel for {node.name}') +",
            f"       REPLACE",
            "",
        ])

        # 4. Cluster-Sender Channel (CLUSSDR)
        # Defined to establish the initial handshake with Full Repositories
        lines.extend([
            "* 4. Initial Cluster-Sender Channel(s) (CLUSSDR)",
            "* Used for initial cluster registration and discovery",
        ])

        if not node.cluster_sender_targets:
            lines.append("* [NOTICE] No CLUSSDR targets specified for this Queue Manager.")
        else:
            for target_name in node.cluster_sender_targets:
                target_node = topology.nodes.get(target_name)
                if target_node:
                    target_channel_name = target_node.computed_clusrcvr_name
                    target_conname = target_node.conname
                else:
                    # Fallback default convention
                    target_channel_name = f"TO.{target_name}"
                    target_conname = f"localhost({1414})"

                lines.extend([
                    f"DEFINE CHANNEL('{target_channel_name}') +",
                    f"       CHLTYPE(CLUSSDR) +",
                    f"       TRPTYPE(TCP) +",
                    f"       CONNAME('{target_conname}') +",
                    f"       CLUSTER('{cluster_name}') +",
                    f"       DESCR('Cluster sender channel to {target_name}') +",
                    f"       REPLACE",
                ])
        lines.append("")

        # 5. Cluster Queues hosted by this QMgr
        all_queues = list(set(node.queues + topology.cluster_queues))
        if all_queues:
            lines.extend([
                "* 5. Define Cluster Queues",
                "* Workload balancing is enabled using DEFBIND(NOTFIXED)",
            ])
            for q_name in all_queues:
                lines.extend([
                    f"DEFINE QLOCAL('{q_name}') +",
                    f"       CLUSTER('{cluster_name}') +",
                    f"       DEFBIND(NOTFIXED) +",
                    f"       DESCR('Cluster workload-balanced queue for {cluster_name}') +",
                    f"       REPLACE",
                ])
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def generate_all_scripts(cls, topology: ClusterTopology) -> Dict[str, str]:
        """
        Generates MQSC script content for each Queue Manager in the topology.
        Returns a dict: {qmgr_name: mqsc_content}
        """
        # Ensure channels are auto-wired if not set
        cls.auto_wire_topology(topology)

        scripts = {}
        for qm_name in topology.nodes.keys():
            scripts[qm_name] = cls.generate_qmgr_script(topology, qm_name)
        return scripts

    @classmethod
    def generate_verification_script(cls, topology: ClusterTopology) -> str:
        """
        Generates verification MQSC commands to check cluster health and channels.
        """
        return "\n".join([
            "* ==================================================================",
            f"* Verification commands for Cluster: {topology.cluster_name}",
            "* ==================================================================",
            "* Check local queue manager state",
            "DISPLAY QMSTATUS",
            "",
            "* Display all known Queue Managers in this cluster",
            f"DISPLAY CLUSQMGR(*) CLUSTER('{topology.cluster_name}') ALL",
            "",
            "* Display cluster channels and operational status",
            "DISPLAY CHSTATUS('TO.*')",
            "",
            "* Display all cluster queues known in the cluster",
            f"DISPLAY QCLUSTER(*) CLUSTER('{topology.cluster_name}')",
            "",
        ])

    @classmethod
    def generate_teardown_script(cls, topology: ClusterTopology, qm_name: str) -> str:
        """
        Generates cleanup commands to remove a Queue Manager from the cluster.
        """
        node = topology.nodes.get(qm_name)
        cluster_name = topology.cluster_name
        clusrcvr_name = node.computed_clusrcvr_name if node else f"TO.{qm_name}"

        return "\n".join([
            f"* ==================================================================",
            f"* Teardown / Leave Cluster Script for {qm_name}",
            f"* ==================================================================",
            f"* 1. Suspend membership in cluster",
            f"SUSPEND QMGR CLUSTER('{cluster_name}')",
            "",
            f"* 2. Remove cluster queues",
            *[f"ALTER QLOCAL('{q}') CLUSTER(' ') NOCLUSTER" for q in topology.cluster_queues],
            "",
            f"* 3. Remove cluster receiver channel",
            f"ALTER CHANNEL('{clusrcvr_name}') CHLTYPE(CLUSRCVR) CLUSTER(' ')",
            "",
            f"* 4. Clear repository role (if Full Repository)",
            f"ALTER QMGR REPOS(' ')",
            "",
            f"* 5. Refresh cluster repository cache",
            f"REFRESH CLUSTER('{cluster_name}') REPOS(YES)",
            "",
        ])

    @classmethod
    def write_scripts_to_disk(cls, topology: ClusterTopology, output_dir: Path) -> Dict[str, Path]:
        """
        Writes all generated MQSC files to output_dir.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        scripts = cls.generate_all_scripts(topology)
        written_files = {}

        for qm_name, content in scripts.items():
            file_path = output_dir / f"{qm_name}.mqsc"
            file_path.write_text(content, encoding="utf-8")
            written_files[qm_name] = file_path

        # Also write verification script
        verify_path = output_dir / f"{topology.cluster_name}_verify.mqsc"
        verify_path.write_text(cls.generate_verification_script(topology), encoding="utf-8")
        written_files["verify"] = verify_path

        return written_files

