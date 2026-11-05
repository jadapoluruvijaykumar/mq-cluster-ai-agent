import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from ..models import ClusterTopology, QMgrRole
from ..generator import MQSCGenerator


class DockerOrchestrator:
    """
    Generates ready-to-run Docker Compose environments for testing IBM MQ Clusters
    locally using the official IBM MQ developer container images.
    """

    DEFAULT_IMAGE = "icr.io/ibm-com/mq:latest"

    @classmethod
    def generate_docker_compose_dict(
        cls,
        topology: ClusterTopology,
        image: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates the Docker Compose YAML structure for the cluster.
        Configures internal network routing so containers communicate by hostname.
        """
        image_name = image or cls.DEFAULT_IMAGE
        services: Dict[str, Any] = {}

        for qm_name, node in topology.nodes.items():
            service_name = qm_name.lower().replace("_", "-")
            services[service_name] = {
                "image": image_name,
                "container_name": service_name,
                "hostname": service_name,
                "environment": [
                    "LICENSE=accept",
                    f"MQ_QMGR_NAME={node.name}",
                    "MQ_ENABLE_METRICS=false",
                    "MQ_DEV=true",
                    "MQ_ADMIN_PASSWORD=pass"
                ],
                "ports": [
                    f"{node.port}:1414",
                    f"{node.rest_port}:9443"
                ],
                "volumes": [
                    f"./mqsc/{node.name}.mqsc:/etc/mqm/20-cluster.mqsc:ro"
                ],
                "networks": ["mq-cluster-net"]
            }

        compose_doc = {
            "version": "3.8",
            "networks": {
                "mq-cluster-net": {
                    "driver": "bridge"
                }
            },
            "services": services
        }

        return compose_doc

    @classmethod
    def generate_docker_lab(
        cls,
        topology: ClusterTopology,
        output_dir: Path,
        image: Optional[str] = None
    ) -> Path:
        """
        Generates both the docker-compose.yml and the container-adjusted MQSC files.
        Inside docker network, each QMgr reaches others via container hostnames.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        mqsc_dir = output_dir / "mqsc"
        mqsc_dir.mkdir(parents=True, exist_ok=True)

        # Create a container-network-adjusted topology copy
        docker_topology = topology.model_copy(deep=True)
        for qm_name, node in docker_topology.nodes.items():
            # In container bridge network, hostname is the service name and internal port is 1414
            node.host = qm_name.lower().replace("_", "-")
            node.port = 1414

        # Generate container MQSC scripts
        MQSCGenerator.write_scripts_to_disk(docker_topology, mqsc_dir)

        # Generate compose file
        compose_dict = cls.generate_docker_compose_dict(topology, image)
        compose_path = output_dir / "docker-compose.yml"

        with open(compose_path, "w", encoding="utf-8") as f:
            yaml.dump(compose_dict, f, default_flow_style=False, sort_keys=False)

        # Create quickstart helper scripts
        readme_path = output_dir / "README.md"
        readme_path.write_text(cls._generate_lab_readme(topology), encoding="utf-8")

        return compose_path

    @classmethod
    def _generate_lab_readme(cls, topology: ClusterTopology) -> str:
        fr_names = ", ".join(fr.name for fr in topology.full_repositories)
        pr_names = ", ".join(pr.name for pr in topology.partial_repositories) or "None"
        return f"""# IBM MQ Cluster Local Docker Lab: {topology.cluster_name}

## Cluster Overview
- **Cluster Name**: `{topology.cluster_name}`
- **Full Repositories**: `{fr_names}`
- **Partial Repositories**: `{pr_names}`
- **Cluster Queues**: `{", ".join(topology.cluster_queues) or "None"}`

## Quickstart

### 1. Start the cluster:
```bash
docker compose up -d
```

### 2. Verify cluster status:
Check cluster queue managers from any node:
```bash
docker exec -it {topology.full_repositories[0].name.lower().replace("_", "-")} runmqsc {topology.full_repositories[0].name}
# Inside runmqsc:
DISPLAY CLUSQMGR(*)
DISPLAY CHSTATUS(TO.*)
```

### 3. Web Console / REST API:
Access the IBM MQ Console at:
- {topology.full_repositories[0].name}: `https://localhost:{topology.full_repositories[0].rest_port}/ibmmq/console`
  - User: `admin`
  - Password: `pass`

### 4. Stop the cluster:
```bash
docker compose down
```
"""
