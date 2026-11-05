import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown

from config import OUTPUT_DIR, MQSC_OUTPUT_DIR, DOCKER_OUTPUT_DIR
from mq_agent import MQClusterAgent, ExecutionMode, QMgrRole


console = Console()


def print_banner():
    banner = r"""
  ___ ____  __  __   __  __  ___       _    ___      _                    _   
 |_ _| __ )|  \/  | |  \/  |/ _ \     / \  |_ _|    / \   __ _  ___ _ __ | |_ 
  | ||  _ \| |\/| | | |\/| | | | |   / _ \  | |    / _ \ / _` |/ _ \ '_ \| __|
  | || |_) | |  | | | |  | | |_| |  / ___ \ | |   / ___ \ (_| |  __/ | | | |_ 
 |___|____/|_|  |_| |_|  |_|\__\_\ /_/   \_\___| /_/   \_\__, |\___|_| |_|\__|
                                                         |___/                
         IBM MQ Cluster AI Architect & Automation Engine
"""
    console.print(Panel(banner, style="bold cyan", border_style="blue"))


def display_topology(agent: MQClusterAgent):
    if not agent.current_topology:
        console.print("[yellow]No cluster topology has been planned yet.[/yellow]")
        return

    top = agent.current_topology

    # Summary Panel
    summary_text = (
        f"[bold]Cluster Name:[/bold] [cyan]{top.cluster_name}[/cyan]\n"
        f"[bold]Total Queue Managers:[/bold] {len(top.nodes)}\n"
        f"[bold]Full Repositories (FR):[/bold] {', '.join(fr.name for fr in top.full_repositories)}\n"
        f"[bold]Partial Repositories (PR):[/bold] {', '.join(pr.name for pr in top.partial_repositories) or 'None'}\n"
        f"[bold]Cluster Queues:[/bold] {', '.join(top.cluster_queues) or 'None'}"
    )
    console.print(Panel(summary_text, title="Active Cluster Topology", border_style="green"))

    # Table of Nodes & Channels
    table = Table(title="Queue Manager Endpoints & Channel Wiring", border_style="cyan")
    table.add_column("QMgr Name", style="bold white")
    table.add_column("Role", style="yellow")
    table.add_column("Host:Port", style="green")
    table.add_column("CLUSRCVR Channel", style="cyan")
    table.add_column("CLUSSDR Targets", style="magenta")

    for node in top.nodes.values():
        role_label = "[bold red]FULL REPO[/bold red]" if node.role == QMgrRole.FULL_REPOSITORY else "PARTIAL REPO"
        table.add_row(
            node.name,
            role_label,
            node.conname,
            node.computed_clusrcvr_name,
            ", ".join(f"TO.{tgt}" for tgt in node.cluster_sender_targets) or "[dim]None[/dim]"
        )

    console.print(table)


def display_validation(agent: MQClusterAgent):
    if not agent.current_topology:
        console.print("[yellow]No active topology to validate.[/yellow]")
        return

    val = agent.current_topology
    from mq_agent.validator import ClusterValidator
    res = ClusterValidator.validate(val)

    if res.is_valid:
        console.print("\n[bold green]✔ Validation Passed: Topology meets IBM MQ High-Availability standards.[/bold green]")
    else:
        console.print("\n[bold red]✖ Validation Failed with Errors:[/bold red]")
        for err in res.errors:
            console.print(f"  [red]• {err}[/red]")

    if res.warnings:
        console.print("\n[bold yellow]⚠ Architectural Warnings:[/bold yellow]")
        for w in res.warnings:
            console.print(f"  [yellow]• {w}[/yellow]")

    if res.recommendations:
        console.print("\n[bold cyan]💡 IBM Best-Practice Recommendations:[/bold cyan]")
        for r in res.recommendations:
            console.print(f"  [cyan]• {r}[/cyan]")


def interactive_loop(agent: MQClusterAgent):
    print_banner()
    console.print("[bold]Type your cluster request in plain English, or use shortcuts:[/bold]")
    console.print("  [cyan]create[/cyan]    - Run step-by-step cluster creation wizard")
    console.print("  [cyan]show[/cyan]      - Display current cluster topology table")
    console.print("  [cyan]validate[/cyan]  - Validate current topology")
    console.print("  [cyan]generate[/cyan]  - Generate and view MQSC files")
    console.print("  [cyan]docker[/cyan]    - Generate Docker Compose lab environment")
    console.print("  [cyan]simulate[/cyan]  - Run simulated dry-run execution")
    console.print("  [cyan]diagnose[/cyan]  - Diagnose an MQ error code (e.g. diagnose AMQ9448)")
    console.print("  [cyan]exit[/cyan]      - Exit agent\n")

    while True:
        try:
            user_input = console.input("[bold green]MQ-Agent > [/bold green]").strip()
            if not user_input:
                continue

            cmd_lower = user_input.lower()

            if cmd_lower in ["exit", "quit", "q"]:
                console.print("[cyan]Goodbye![/cyan]")
                break

            elif cmd_lower == "show":
                display_topology(agent)

            elif cmd_lower == "validate":
                display_validation(agent)

            elif cmd_lower == "create":
                # Step-by-step wizard
                cluster_name = console.input("[cyan]Enter Cluster Name (e.g. PAYMENT_CLUS): [/cyan]").strip().upper() or "DEFAULT_CLUS"
                fr_input = console.input("[cyan]Enter Full Repositories comma-separated (e.g. QM1, QM2): [/cyan]").strip().upper() or "QM1, QM2"
                pr_input = console.input("[cyan]Enter Partial Repositories comma-separated (e.g. QM3, QM4) [optional]: [/cyan]").strip().upper()
                q_input = console.input("[cyan]Enter Cluster Queues comma-separated (e.g. ORDERS.IN) [optional]: [/cyan]").strip().upper()

                full_repos = [x.strip() for x in fr_input.split(",") if x.strip()]
                partial_repos = [x.strip() for x in pr_input.split(",") if x.strip()]
                queues = [x.strip() for x in q_input.split(",") if x.strip()]

                agent.plan(
                    cluster_name=cluster_name,
                    full_repositories=full_repos,
                    partial_repositories=partial_repos,
                    cluster_queues=queues
                )
                console.print("[bold green]Cluster topology planned successfully![/bold green]")
                display_topology(agent)
                display_validation(agent)

            elif cmd_lower in ["generate", "mqsc"]:
                if not agent.current_topology:
                    console.print("[yellow]Plan a cluster first by typing 'create' or asking in natural language.[/yellow]")
                    continue
                files = agent.generate()
                console.print("\n[bold green]MQSC Scripts Generated Successfully:[/bold green]")
                for name, path in files.items():
                    console.print(f"  • [cyan]{name}[/cyan]: {path.resolve()}")

                # Preview first script
                first_node = list(agent.current_topology.nodes.keys())[0]
                first_script = files.get(first_node)
                if first_script:
                    console.print(f"\n[bold]Preview: {first_script.name}[/bold]")
                    syntax = Syntax(first_script.read_text(encoding="utf-8"), "sql", theme="monokai", line_numbers=True)
                    console.print(syntax)

            elif cmd_lower in ["docker", "compose"]:
                if not agent.current_topology:
                    console.print("[yellow]Plan a cluster first.[/yellow]")
                    continue
                compose_file = agent.generate_docker()
                console.print(f"\n[bold green]Docker Compose Lab created at:[/bold green] {compose_file.resolve()}")
                console.print("[bold cyan]To start your multi-node MQ cluster locally:[/bold cyan]")
                console.print(f"  cd {compose_file.parent}")
                console.print("  docker compose up -d\n")

            elif cmd_lower == "simulate":
                if not agent.current_topology:
                    console.print("[yellow]Plan a cluster first.[/yellow]")
                    continue
                res = agent.execute(mode=ExecutionMode.SIMULATION)
                for qm, r in res.items():
                    console.print(f"[bold green]✔ Simulated execution for {qm}: Success[/bold green]")
                    console.print(r.stdout.strip())

            elif cmd_lower.startswith("diagnose"):
                diag_query = user_input[8:].strip()
                ans = agent.ask(f"diagnose {diag_query}")
                console.print(Markdown(ans))

            else:
                # Natural language prompt to AI agent
                response = agent.ask(user_input)
                console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[cyan]Session terminated by user.[/cyan]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="IBM MQ Cluster AI Agent")
    parser.add_argument("--cluster", "-c", type=str, help="Cluster name")
    parser.add_argument("--fr", type=str, help="Full Repositories (comma-separated, e.g. QM1,QM2)")
    parser.add_argument("--pr", type=str, help="Partial Repositories (comma-separated, e.g. QM3,QM4)")
    parser.add_argument("--queues", "-q", type=str, help="Cluster Queues (comma-separated)")
    parser.add_argument("--docker", action="store_true", help="Generate Docker Compose lab environment")
    parser.add_argument("--generate", action="store_true", help="Generate MQSC scripts to disk")

    args = parser.parse_args()
    agent = MQClusterAgent(output_dir=OUTPUT_DIR)

    if args.cluster and args.fr:
        full_repos = [x.strip() for x in args.fr.split(",") if x.strip()]
        partial_repos = [x.strip() for x in args.pr.split(",") if x.strip()] if args.pr else []
        queues = [x.strip() for x in args.queues.split(",") if x.strip()] if args.queues else []

        agent.plan(
            cluster_name=args.cluster,
            full_repositories=full_repos,
            partial_repositories=partial_repos,
            cluster_queues=queues
        )
        display_topology(agent)
        display_validation(agent)

        if args.generate:
            files = agent.generate()
            console.print("[green]Generated MQSC scripts:[/green]")
            for k, p in files.items():
                console.print(f"  {k}: {p}")

        if args.docker:
            d_file = agent.generate_docker()
            console.print(f"[green]Generated Docker Compose lab at {d_file}[/green]")

    else:
        interactive_loop(agent)


if __name__ == "__main__":
    main()
