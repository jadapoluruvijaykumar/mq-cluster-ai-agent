# IBM MQ Cluster AI Agent in Python

An intelligent AI Agent designed to plan, validate, generate, orchestrate, and troubleshoot **IBM MQ Clusters**. 

The agent automatically handles repository architecture (Full vs. Partial), CLUSRCVR/CLUSSDR channel wiring, listener ports, cluster queues with workload balancing (`DEFBIND(NOTFIXED)`), and containerized local lab environments.

---

## 🚀 Key Features

- **Automated Topology Planning & Auto-Wiring**:
  - Automatically identifies and wires High-Availability (HA) Full Repositories (FR) to each other.
  - Automatically wires Partial Repositories (PR) to both Full Repositories for redundancy.
  - Generates standard IBM MQ naming conventions (`TO.<QMGR>`).
- **IBM MQ Architecture Validation Engine**:
  - **HA Resiliency Check**: Flags single-point-of-failure if only 1 FR is configured; warns if > 2 FRs are defined.
  - **Channel Length Limits**: Enforces IBM MQ's strict 20-character limit on channel names (`TO.<QMGR>`).
  - **Port Collision Detection**: Prevents listener port overlaps on the same host.
  - **Workload Balancing Check**: Recommends `DEFBIND(NOTFIXED)` on cluster queues.
- **Multiple Execution Backends**:
  - **Simulation / Dry-Run**: Validates syntax and generates files without requiring a running MQ server.
  - **Docker Compose Lab Generator**: Creates a turnkey multi-node IBM MQ cluster sandbox using official `icr.io/ibm-com/mq` containers.
  - **Local CLI (`runmqsc`)**: Executes directly via the local IBM MQ CLI.
  - **IBM MQ Administrative REST API**: Executes commands over HTTPS with CSRF tokens.
- **Built-in Cluster Diagnostics**:
  - Instant diagnosis and remediation recipes for common MQ cluster issues (`AMQ9448`, `AMQ9457`, `AMQ9514`, `AMQ9202`, channel retrying, split repositories, etc.).
- **Dual AI Orchestration**:
  - Works with **Google Gemini** or **OpenAI** for natural-language agentic workflows.
  - Includes a zero-dependency **Offline Expert Engine** that works immediately without API keys!

---

## 🌐 FastAPI + LangGraph Web Architecture

In addition to the terminal CLI, the project includes a full **FastAPI** backend coupled with a **LangGraph** state machine.

### LangGraph Agent State Machine:
```
           ┌────────────────────────┐
           │        [START]         │
           └───────────┬────────────┘
                       │
                       ▼
           ┌────────────────────────┐
           │     analyze_intent     │
           └───────────┬────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
  [create_cluster] [diagnose]    [general]
         │             │             │
         ▼             │             │
  ┌──────────────┐     │             │
  │ plan_cluster │     │             │
  └──────┬───────┘     │             │
         ▼             │             │
┌──────────────────┐   │             │
│ validate_cluster │   │             │
└────────┬─────────┘   │             │
         ▼             │             │
 ┌───────────────┐     │             │
 │ generate_mqsc │     │             │
 └───────┬───────┘     │             │
         │             │             │
         └─────────────┼─────────────┘
                       │
                       ▼
           ┌────────────────────────┐
           │        respond         │
           └───────────┬────────────┘
                       │
                       ▼
           ┌────────────────────────┐
           │         [END]          │
           └────────────────────────┘
```

### Launch the Web UI & API Server:
```bash
python cli.py --serve
# or:
python api.py
```
Open your browser at:
- **Interactive Web UI**: [http://localhost:8000](http://localhost:8000)
- **OpenAPI / Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### API Endpoints:
- `POST /api/chat`: Natural language cluster design & troubleshooting via the LangGraph agent.
- `POST /api/cluster/plan`: Structured JSON topology planner & auto-wirer.
- `POST /api/cluster/generate`: Generates MQSC configuration scripts.
- `GET /api/cluster/docker-preview`: Returns containerized `docker-compose.yml`.
- `GET /api/cluster/diagnose?query=...`: Diagnostic lookup for IBM MQ cluster errors (`AMQ9448`, `AMQ9202`, etc.).
- `GET /api/health`: Health status and active cluster indicator.

---

## 🤖 Antigravity Skill Agent Integration

This codebase is packaged directly as an **Antigravity Skill Agent** located in [`.agent/skills/ibm-mq-cluster/SKILL.md`](.agent/skills/ibm-mq-cluster/SKILL.md).

### How It Works:
1. **Progressive Disclosure**: Antigravity automatically detects the skill description whenever you or another agent asks about IBM MQ clustering.
2. **Automatic Invocation**: You don't need to manually run scripts; you can simply ask in chat:
   - *"Design an IBM MQ cluster with QM1 and QM2 as Full Repositories and QM3 as a Partial Repository."*
   - *"Why is my cluster sender channel in RETRYING status?"*
   - *"Generate a 3-node MQ cluster Docker compose file."*
3. **Dedicated Subagent**:
   - Registered as `ibm-mq-cluster-agent`.
   - Antigravity can invoke it as an autonomous background subagent to handle long-running cluster deployments and verification workflows.

---

```
d:\IBM_MQ_Agent\
├── .agent/
│   └── skills/
│       └── ibm-mq-cluster/
│           └── SKILL.md          # Antigravity Workspace Skill definition
├── mq_agent/
│   ├── __init__.py
│   ├── models.py                 # Pydantic data models (Topology, QMgrNode, ChannelDef)
│   ├── generator.py              # Industry-standard MQSC generator
│   ├── validator.py              # IBM MQ best-practice rule validator
│   ├── diagnostics.py            # Expert error diagnosis knowledge base
│   ├── tools.py                  # Agent tool functions
│   ├── agent.py                  # Orchestrator (Gemini / OpenAI / Offline Expert)
│   ├── langgraph_agent.py        # LangGraph StateGraph agent workflow
│   └── executors/
│       ├── base.py               # Abstract executor interface
│       ├── mock_executor.py      # Dry-run simulator
│       ├── cli_executor.py       # runmqsc execution engine
│       ├── rest_executor.py      # IBM MQ Admin REST API client
│       └── docker_orchestrator.py# Docker Compose lab generator
├── web/
│   └── index.html                # Interactive single-page dashboard & topology viewer
├── api.py                        # FastAPI backend application
├── cli.py                        # Rich interactive terminal UI
├── example.py                    # Programmatic Python example
├── tests/
│   ├── test_cluster_generator.py # Core cluster generation tests
│   └── test_api_and_langgraph.py # FastAPI & LangGraph integration tests
├── requirements.txt
├── config.py
└── .env.example
```

---

## 🛠️ Quick Start

### 1. Requirements & Setup

Dependencies are already installed in your Python environment. If needed elsewhere:
```bash
pip install -r requirements.txt
```

*(Optional)* Configure API keys in `.env` if you wish to use Gemini or OpenAI:
```bash
cp .env.example .env
# Edit .env with your GEMINI_API_KEY or OPENAI_API_KEY
```
> **Note**: Even without any API keys, the agent works offline out-of-the-box!

---

### 2. Interactive Terminal UI

Start the interactive terminal UI:
```bash
python cli.py
```

Inside the CLI, you can type commands or natural language:
```text
MQ-Agent > create
Enter Cluster Name: PAYMENT_CLUS
Enter Full Repositories comma-separated: QM1, QM2
Enter Partial Repositories comma-separated: QM3
Enter Cluster Queues comma-separated: ORDERS.IN

MQ-Agent > show
MQ-Agent > validate
MQ-Agent > generate
MQ-Agent > docker
MQ-Agent > simulate
MQ-Agent > diagnose AMQ9448
```

Or speak in plain English:
```text
MQ-Agent > Create cluster INVENTORY_CLUS with FR QM1, QM2 and PR QM3 and queue INVENTORY.UPDATES
```

---

### 3. Command Line Batch Mode

You can generate an entire cluster and its Docker lab in a single command:
```bash
python cli.py --cluster "PAYMENT_CLUS" --fr "QM1,QM2" --pr "QM3" --queues "PAYMENT.REQ" --generate --docker
```

Output files will be written to:
- `output/mqsc/` -> Individual `.mqsc` scripts for each Queue Manager + cluster verification script.
- `output/docker/` -> `docker-compose.yml` and container-ready configuration.

---

### 4. Running the Multi-Node Cluster with Docker

Once generated, launch your live 3-node cluster locally:
```bash
cd output/docker
docker compose up -d
```

Verify the cluster status:
```bash
docker exec -it qm1 runmqsc QM1
# Inside runmqsc:
DISPLAY CLUSQMGR(*)
DISPLAY CHSTATUS(TO.*)
```

Web Console:
- Access `QM1`: `https://localhost:9443/ibmmq/console` (User: `admin` / Password: `pass`)
- Access `QM2`: `https://localhost:9444/ibmmq/console`
- Access `QM3`: `https://localhost:9445/ibmmq/console`

---

### 5. Python Programmatic Usage

You can embed the agent directly into your Python pipelines:

```python
from mq_agent import MQClusterAgent, ExecutionMode

# Initialize agent
agent = MQClusterAgent()

# 1. Natural language cluster creation
response = agent.ask("Create cluster ORDER_CLUS with FR QM1, QM2 and PR QM3 and queue ORDERS.IN")
print(response)

# 2. Write validated MQSC scripts to disk
generated_files = agent.generate()
print(f"Generated scripts: {list(generated_files.keys())}")

# 3. Generate Docker compose lab
docker_file = agent.generate_docker()
print(f"Docker compose file: {docker_file}")

# 4. Run dry-run simulation
sim_results = agent.execute(mode=ExecutionMode.SIMULATION)
for qm, result in sim_results.items():
    print(f"QMgr {qm}: {result.stdout.strip()}")
```

---

### 6. Run Unit Tests

```bash
python -m pytest tests/
```
All tests verify topology auto-wiring, channel name bounds, HA warnings, MQSC syntax, and Docker generation.

