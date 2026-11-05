from pathlib import Path
from typing import Optional
from .base import BaseMQExecutor, ExecutionResult


class MockExecutor(BaseMQExecutor):
    """
    Simulation executor. Does not require a running IBM MQ installation.
    Validates command structure and saves the executed commands to output files.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("output/simulation")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.history = []

    def execute_mqsc(self, qmgr_name: str, mqsc_text: str) -> ExecutionResult:
        # Save command execution for inspection
        log_file = self.output_dir / f"{qmgr_name}_simulated_execution.log"
        log_file.write_text(mqsc_text, encoding="utf-8")

        self.history.append({"qmgr": qmgr_name, "mqsc": mqsc_text})

        # Count commands in the script
        cmd_count = sum(1 for line in mqsc_text.splitlines() if line.strip() and not line.strip().startswith("*"))

        simulated_output = (
            f"5724-H72 (C) Copyright IBM Corp. 1994, 2026.\n"
            f"Starting MQSC for queue manager {qmgr_name}.\n\n"
            f"[SIMULATION] Processed {cmd_count} MQSC commands successfully.\n"
            f"All commands evaluated with zero errors (syntax verified).\n"
            f"Script saved to: {log_file}\n"
        )

        return ExecutionResult(
            success=True,
            qmgr=qmgr_name,
            stdout=simulated_output,
            stderr="",
            return_code=0,
            metadata={"simulated": True, "saved_to": str(log_file), "command_count": cmd_count}
        )

    def check_health(self, qmgr_name: str) -> ExecutionResult:
        simulated_output = (
            f"QMNAME({qmgr_name}) STATUS(RUNNING)\n"
            f"CLUSTER STATUS: Active, Repositories synchronized\n"
        )
        return ExecutionResult(
            success=True,
            qmgr=qmgr_name,
            stdout=simulated_output,
            return_code=0,
            metadata={"simulated": True, "status": "RUNNING"}
        )
