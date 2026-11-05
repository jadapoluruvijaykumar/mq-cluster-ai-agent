"""
Example: Using the IBM MQ Cluster AI Agent programmatically in Python
"""

from mq_agent import MQClusterAgent, ExecutionMode

def main():
    # 1. Initialize the agent (offline expert engine for instant demonstration)
    agent = MQClusterAgent(provider="offline")

    print("\n--- 1. Natural Language Interaction ---")
    response = agent.ask("Create cluster ORDER_CLUSTER with FR QM_FR1, QM_FR2 and PR QM_PR1 and queue ORDERS.IN")
    print(response)

    print("\n--- 2. Generating MQSC Scripts ---")
    generated_files = agent.generate()
    for name, path in generated_files.items():
        print(f"Generated: {name} -> {path}")

    print("\n--- 3. Running Dry-Run Simulation ---")
    results = agent.execute(mode=ExecutionMode.SIMULATION)
    for qm, result in results.items():
        print(f"Simulation for {qm}: Success={result.success}")

    print("\n--- 4. Diagnosing Cluster Issues ---")
    diag_res = agent.ask("diagnose AMQ9448")
    print(diag_res)


if __name__ == "__main__":
    main()
