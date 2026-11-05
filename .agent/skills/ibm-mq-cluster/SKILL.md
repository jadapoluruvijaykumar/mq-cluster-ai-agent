---
name: ibm-mq-cluster
description: >-
  Expert architect and automation skill for IBM MQ Clusters. Use this skill when
  the user asks to design, plan, validate, configure, generate MQSC scripts for,
  deploy, or troubleshoot an IBM MQ Cluster (Full Repositories, Partial Repositories,
  CLUSRCVR, CLUSSDR channels, cluster queues, workload balancing, local Docker sandbox,
  or diagnosing AMQ9448, AMQ9457, AMQ9202, AMQ9514 cluster errors).
---

# IBM MQ Cluster Architect & Automation Skill

This skill allows the agent to act as an expert IBM MQ Systems Architect and Administrator. It provides tools to automatically plan, validate, generate, and troubleshoot IBM MQ Clusters.

---

## 🛠️ When to Use This Skill

Activate this skill whenever the user asks to:
1. **Plan or create a new IBM MQ Cluster** (e.g. defining Full Repositories and Partial Repositories).
2. **Generate MQSC scripts** for cluster setup, channel cross-connection, or cluster queues.
3. **Validate an existing cluster topology** against High Availability (HA) rules, channel name limits, and workload balancing standards.
4. **Deploy a local containerized cluster lab** using Docker Compose.
5. **Diagnose and troubleshoot cluster issues** such as channels in `RETRYING`/`STOPPED` status, split repositories, `AMQ9448`, `AMQ9457`, or messages not balancing across queues.

---

## 📐 IBM MQ Clustering Golden Rules

1. **High Availability (HA)**: A production cluster must have **exactly 2 Full Repositories (FR)**. Having 1 FR creates a Single Point of Failure (SPOF); having > 2 creates unnecessary gossip and cache synchronization overhead.
2. **Channel Name Limit**: IBM MQ channel names **cannot exceed 20 characters**. The standard naming convention is `TO.<QMGR_NAME>`. Ensure `len("TO." + qmgr_name) <= 20`.
3. **Queue / QMgr Name Limit**: Queue manager names and cluster queue names cannot exceed **48 characters**.
4. **Channel Connectivity**:
   - Each Queue Manager must define a Cluster Receiver (`CLUSRCVR`) channel with a valid `CONNAME(host(port))`.
   - Full Repositories must have Cluster Sender (`CLUSSDR`) channels pointing to the other Full Repository.
   - Partial Repositories must define initial `CLUSSDR` channels pointing to the Full Repositories.
5. **Workload Balancing**: Cluster queues must be defined with `DEFBIND(NOTFIXED)` so messages are distributed round-robin across instances rather than pinned to a single connection.

---

## 🚀 Execution Procedures

### 1. Batch Cluster Planning & Generation
To plan a cluster, validate it, and generate both MQSC files and a Docker sandbox in one step:

```powershell
python cli.py --cluster "<CLUSTER_NAME>" --fr "<FR1,FR2>" --pr "<PR1>" --queues "<QUEUE1>" --generate --docker
```

Artifacts will be written to:
- `output/mqsc/<QMGR>.mqsc` -> Individual MQSC setup scripts
- `output/mqsc/<CLUSTER_NAME>_verify.mqsc` -> Cluster health verification script
- `output/docker/docker-compose.yml` -> 3-node containerized local lab

---

### 2. Launching the Interactive Web UI & REST API
To launch the interactive LangGraph Web UI and Swagger REST API:

```powershell
python cli.py --serve
# Accessible at http://localhost:8000
```

---

### 3. Programmatic Invocation via Python

```python
from mq_agent import MQClusterAgent, ExecutionMode

agent = MQClusterAgent()

# Natural language cluster planning
response = agent.ask("Create cluster PAYMENT_CLUS with FR QM1, QM2 and PR QM3 and queue ORDERS.IN")

# Generate MQSC files
files = agent.generate()

# Generate Docker lab
compose_file = agent.generate_docker()
```

---

### 4. Diagnosing Cluster Errors
To troubleshoot cluster errors or symptoms, invoke the built-in diagnostic advisor:

```python
from mq_agent.tools import diagnose

advice = diagnose("AMQ9448")
for item in advice:
    print(f"Code: {item.code_or_symptom}")
    print(f"Cause: {item.cause}")
    print(f"Steps: {item.remediation_steps}")
```

Key error codes recognized:
- `AMQ9448`: Repository command returned an error / cache out of sync -> `REFRESH CLUSTER(...) REPOS(YES)`.
- `AMQ9457`: Repository update received for unknown QMgr -> `RESET CLUSTER(...) ACTION(FORCEREMOVE)`.
- `AMQ9514`: Channel stopped due to retries -> Inspect logs and run `START CHANNEL(...)`.
- `AMQ9202`: Connection refused -> Listener stopped or firewall issue.
- `CHANNEL_RETRYING`: CONNAME or network reachability issue.
- `WORKLOAD_NOT_BALANCING`: Check if queue has `DEFBIND(FIXED)` instead of `DEFBIND(NOTFIXED)`.

