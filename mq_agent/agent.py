import os
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from .models import ClusterTopology, ExecutionMode, ValidationResult
from .tools import (
    plan_cluster_topology,
    validate_topology,
    generate_scripts,
    generate_docker_lab,
    execute_cluster,
    diagnose,
)
from .generator import MQSCGenerator


class MQClusterAgent:
    """
    AI Agent for designing, validating, orchestrating, and diagnosing
    IBM MQ Clusters. Supports both LLM-driven mode (Gemini / OpenAI)
    and an offline Expert Rule Engine mode.
    """

    SYSTEM_PROMPT = """
You are an expert IBM MQ Systems Architect and Administrator AI Agent.
Your role is to assist users in planning, validating, generating MQSC configuration,
deploying, and troubleshooting IBM MQ Clusters.

Core Rules & Best Practices:
1. Every IBM MQ cluster requires at least one Full Repository (FR), and IBM strongly recommends exactly two FRs for High Availability (HA) to prevent split-brain and single points of failure.
2. Channel names in IBM MQ cannot exceed 20 characters (e.g. TO.<QMGR_NAME> must be <= 20 chars).
3. Queue Manager names and Cluster names cannot exceed 48 characters.
4. Each Queue Manager must have a CLUSRCVR channel with a valid CONNAME host(port).
5. CLUSSDR channels are used for initial connection to Full Repositories.
6. Cluster Queues should specify DEFBIND(NOTFIXED) for round-robin message-by-message workload balancing.
7. Available tools:
   - plan_cluster_topology(cluster_name, full_repositories, partial_repositories, cluster_queues)
   - validate_topology()
   - generate_scripts(output_dir)
   - generate_docker_lab(output_dir)
   - diagnose(query)

Always provide clear, production-ready MQSC commands and highlight architectural risks or warnings.
"""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        provider: Optional[str] = None,
        output_dir: Optional[Path] = None
    ):
        self.provider = (provider or os.getenv("DEFAULT_LLM_PROVIDER", "auto")).lower()
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.output_dir = output_dir or Path("output")
        self.current_topology: Optional[ClusterTopology] = None

        # Determine LLM availability
        self.has_gemini = bool(self.gemini_api_key) and self.provider in ["auto", "gemini"]
        self.has_openai = bool(self.openai_api_key) and self.provider in ["auto", "openai"]

    def plan(
        self,
        cluster_name: str,
        full_repositories: List[str],
        partial_repositories: Optional[List[str]] = None,
        host: str = "localhost",
        base_port: int = 1414,
        cluster_queues: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Plans a new IBM MQ Cluster topology and validates it.
        """
        topology = plan_cluster_topology(
            cluster_name=cluster_name,
            full_repositories=full_repositories,
            partial_repositories=partial_repositories,
            host=host,
            base_port=base_port,
            cluster_queues=cluster_queues
        )
        self.current_topology = topology
        validation = validate_topology(topology)

        return {
            "topology": topology,
            "validation": validation,
            "full_repositories": [fr.name for fr in topology.full_repositories],
            "partial_repositories": [pr.name for pr in topology.partial_repositories],
            "channels": [
                {
                    "qmgr": qm.name,
                    "clusrcvr": qm.computed_clusrcvr_name,
                    "conname": qm.conname,
                    "sdr_targets": qm.cluster_sender_targets
                }
                for qm in topology.nodes.values()
            ]
        }

    def generate(self, output_subfolder: str = "mqsc") -> Dict[str, Path]:
        """
        Generates MQSC scripts for the active topology and writes them to disk.
        """
        if not self.current_topology:
            raise ValueError("No active cluster topology. Plan a topology first using agent.plan(...)")

        target_dir = self.output_dir / output_subfolder
        return generate_scripts(self.current_topology, target_dir)

    def generate_docker(self, output_subfolder: str = "docker") -> Path:
        """
        Generates a Docker Compose environment for testing the cluster locally.
        """
        if not self.current_topology:
            raise ValueError("No active cluster topology. Plan a topology first using agent.plan(...)")

        target_dir = self.output_dir / output_subfolder
        return generate_docker_lab(self.current_topology, target_dir)

    def execute(self, mode: ExecutionMode = ExecutionMode.SIMULATION) -> Dict[str, Any]:
        """
        Executes the MQSC deployment against the specified backend.
        """
        if not self.current_topology:
            raise ValueError("No active cluster topology. Plan a topology first.")

        return execute_cluster(self.current_topology, mode=mode)

    def ask(self, prompt: str) -> str:
        """
        Handles natural language interaction.
        Uses Gemini or OpenAI if configured, or falls back to the Expert Rule Parser.
        """
        prompt_clean = prompt.strip()

        # Check if LLM is available
        if self.has_gemini:
            try:
                return self._ask_gemini(prompt_clean)
            except Exception as e:
                # Fallback to offline engine if API call fails
                offline_res = self._ask_expert_engine(prompt_clean)
                return f"[Gemini API Notice: {e}. Falling back to Expert Engine]\n\n{offline_res}"
        elif self.has_openai:
            try:
                return self._ask_openai(prompt_clean)
            except Exception as e:
                offline_res = self._ask_expert_engine(prompt_clean)
                return f"[OpenAI API Notice: {e}. Falling back to Expert Engine]\n\n{offline_res}"
        else:
            return self._ask_expert_engine(prompt_clean)

    def _ask_gemini(self, prompt: str) -> str:
        from google import genai
        client = genai.Client(api_key=self.gemini_api_key)

        context = ""
        if self.current_topology:
            context = f"\nCurrent Active Topology: {self.current_topology.model_dump_json()}"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{self.SYSTEM_PROMPT}\n{context}\n\nUser: {prompt}"
        )
        return response.text

    def _ask_openai(self, prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
        ]
        if self.current_topology:
            messages.append({
                "role": "system",
                "content": f"Current Active Topology: {self.current_topology.model_dump_json()}"
            })
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        return response.choices[0].message.content

    def _ask_expert_engine(self, prompt: str) -> str:
        """
        High-precision rule-based parser for offline execution without API keys.
        """
        text = prompt.lower()

        # 1. Diagnose query
        if any(w in text for w in ["amq9", "error", "issue", "troubleshoot", "retrying", "not balancing"]):
            matches = diagnose(prompt)
            if matches:
                output = ["### IBM MQ Cluster Diagnostics\n"]
                for m in matches:
                    output.append(f"**Identified Issue**: {m.code_or_symptom} ({m.category})")
                    output.append(f"**Root Cause**: {m.cause}")
                    output.append("**Recommended Remediation Steps**:")
                    for s in m.remediation_steps:
                        output.append(f"  - {s}")
                    if m.sample_mqsc:
                        output.append(f"\n```mqsc\n{m.sample_mqsc}\n```")
                    output.append("---")
                return "\n".join(output)

        # 2. Intent: Create / Plan a cluster
        if any(w in text for w in ["create", "plan", "build", "setup", "configure"]) and "cluster" in text:
            # Extract cluster name
            clus_match = re.search(r"cluster\s+(?:called\s+|named\s+)?['\"]?([A-Za-z0-9._%]+)['\"]?", prompt, re.IGNORECASE)
            cluster_name = clus_match.group(1).upper() if clus_match else "MY_CLUSTER"

            # Parse FR, PR, Queues cleanly using delimiters
            # Split sections by keywords: with, and, fr, pr, queue(s)
            full_repos = []
            partial_repos = []
            cluster_queues = []

            # Match FR block: between 'fr' or 'full repos...' and the next keyword ('pr', 'partial', 'queue', or end)
            fr_match = re.search(r"(?:fr|full\s*repositor(?:y|ies))\s*[:=]?\s*(.*?)(?=\s+(?:and\s+)?(?:pr|partial|queue)|$)", prompt, re.IGNORECASE)
            if fr_match:
                for item in re.split(r"[,&]|\band\b", fr_match.group(1)):
                    clean = re.sub(r"[^A-Za-z0-9._%]", "", item).upper()
                    if clean:
                        full_repos.append(clean)

            # Match PR block: between 'pr' or 'partial repos...' and next keyword ('queue' or end)
            pr_match = re.search(r"(?:pr|partial\s*repositor(?:y|ies))\s*[:=]?\s*(.*?)(?=\s+(?:and\s+)?(?:queue|fr)|$)", prompt, re.IGNORECASE)
            if pr_match:
                for item in re.split(r"[,&]|\band\b", pr_match.group(1)):
                    clean = re.sub(r"[^A-Za-z0-9._%]", "", item).upper()
                    if clean:
                        partial_repos.append(clean)

            # Match Queue block
            q_match = re.search(r"(?:queue|queues)\s*[:=]?\s*(.*?)(?=\s+(?:and\s+)?(?:fr|pr)|$)", prompt, re.IGNORECASE)
            if q_match:
                for item in re.split(r"[,&]|\band\b", q_match.group(1)):
                    clean = re.sub(r"[^A-Za-z0-9._%]", "", item).upper()
                    if clean:
                        cluster_queues.append(clean)

            # Fallbacks if none matched
            if not full_repos:
                full_repos = ["QM1", "QM2"]

            # Plan topology
            plan_res = self.plan(
                cluster_name=cluster_name,
                full_repositories=full_repos,
                partial_repositories=partial_repos,
                cluster_queues=cluster_queues
            )
            top: ClusterTopology = plan_res["topology"]
            val: ValidationResult = plan_res["validation"]

            out = [
                f"### Planned IBM MQ Cluster: `{top.cluster_name}`",
                "",
                f"- **Full Repositories (FR)**: {', '.join(plan_res['full_repositories'])}",
                f"- **Partial Repositories (PR)**: {', '.join(plan_res['partial_repositories']) if plan_res['partial_repositories'] else 'None'}",
                f"- **Cluster Queues**: {', '.join(top.cluster_queues) if top.cluster_queues else 'None'}",
                "",
                "#### Topology Channels & Connectivity:",
            ]
            for ch in plan_res["channels"]:
                out.append(f"- **{ch['qmgr']}**: CLUSRCVR `{ch['clusrcvr']}` on `{ch['conname']}` | CLUSSDR -> `{', '.join(ch['sdr_targets']) or 'None'}`")

            out.append("\n#### Validation Status:")
            if val.is_valid:
                out.append("✅ **Topology is valid and conforms to IBM MQ best practices!**")
            else:
                out.append("❌ **Validation Errors Found:**")
                for err in val.errors:
                    out.append(f"  - {err}")

            if val.warnings:
                out.append("\n⚠️ **Warnings:**")
                for w in val.warnings:
                    out.append(f"  - {w}")

            if val.recommendations:
                out.append("\n💡 **Recommendations:**")
                for r in val.recommendations:
                    out.append(f"  - {r}")

            out.append("\n**Next Steps:**")
            out.append("1. Type `generate` to write the `.mqsc` scripts to disk.")
            out.append("2. Type `docker` to generate a 100% turnkey local Docker Compose environment.")
            out.append("3. Type `simulate` to run a syntax dry-run.")

            return "\n".join(out)

        # 3. Intent: Generate scripts
        if "generate" in text or "script" in text or "mqsc" in text:
            if not self.current_topology:
                return "No cluster planned yet. Please run: `create cluster <NAME> with FR QM1, QM2 and PR QM3` first."
            files = self.generate()
            out = ["### Generated MQSC Scripts:"]
            for name, path in files.items():
                out.append(f"- **{name}**: `{path.resolve()}`")
            return "\n".join(out)

        # 4. Intent: Docker compose
        if "docker" in text or "container" in text or "compose" in text:
            if not self.current_topology:
                return "No cluster planned yet. Please plan a cluster first."
            compose_path = self.generate_docker()
            return f"### Docker Lab Generated!\n\nLocation: `{compose_path.resolve()}`\n\nRun:\n```bash\ncd {compose_path.parent}\ndocker compose up -d\n```"

        # Default help
        return (
            "### IBM MQ AI Agent Help\n\n"
            "You can ask me to:\n"
            "1. **Create/Plan a cluster**:\n"
            "   `create cluster PAYMENT_CLUS with FR QM1, QM2 and PR QM3, QM4 and queue PAYMENT.IN`\n"
            "2. **Generate MQSC scripts**:\n"
            "   `generate mqsc`\n"
            "3. **Generate Docker environment**:\n"
            "   `generate docker lab`\n"
            "4. **Diagnose cluster errors**:\n"
            "   `diagnose AMQ9448` or `diagnose channel retrying`\n"
        )
