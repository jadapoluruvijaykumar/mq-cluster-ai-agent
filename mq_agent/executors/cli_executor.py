import subprocess
import shutil
from typing import Optional
from .base import BaseMQExecutor, ExecutionResult


class CLIExecutor(BaseMQExecutor):
    """
    Executes commands directly via the local IBM MQ 'runmqsc' CLI.
    Requires IBM MQ client or server binaries to be installed in PATH.
    """

    def __init__(self, runmqsc_path: Optional[str] = None):
        self.runmqsc_path = runmqsc_path or shutil.which("runmqsc") or "runmqsc"

    def is_available(self) -> bool:
        return shutil.which("runmqsc") is not None

    def execute_mqsc(self, qmgr_name: str, mqsc_text: str) -> ExecutionResult:
        if not self.is_available():
            return ExecutionResult(
                success=False,
                qmgr=qmgr_name,
                stderr="The 'runmqsc' executable was not found in PATH. Please verify IBM MQ is installed or use Simulation/REST API mode.",
                return_code=127
            )

        try:
            process = subprocess.Popen(
                [self.runmqsc_path, "-e", qmgr_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=mqsc_text, timeout=30)

            # Check for common IBM MQ errors in stdout
            has_error = False
            if "AMQ8405" in stdout or "AMQ8146" in stdout or "AMQ8149" in stdout:
                has_error = True

            success = (process.returncode == 0) and not has_error

            return ExecutionResult(
                success=success,
                qmgr=qmgr_name,
                stdout=stdout,
                stderr=stderr,
                return_code=process.returncode,
                metadata={"executable": self.runmqsc_path}
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                qmgr=qmgr_name,
                stderr="Execution timed out after 30 seconds.",
                return_code=-1
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                qmgr=qmgr_name,
                stderr=f"Exception running runmqsc: {str(e)}",
                return_code=-1
            )

    def check_health(self, qmgr_name: str) -> ExecutionResult:
        # Check dspmq status
        dspmq = shutil.which("dspmq")
        if not dspmq:
            return self.execute_mqsc(qmgr_name, "DISPLAY QMSTATUS")

        try:
            res = subprocess.run([dspmq, "-m", qmgr_name], capture_output=True, text=True, timeout=10)
            return ExecutionResult(
                success=(res.returncode == 0),
                qmgr=qmgr_name,
                stdout=res.stdout,
                stderr=res.stderr,
                return_code=res.returncode
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                qmgr=qmgr_name,
                stderr=str(e),
                return_code=-1
            )

