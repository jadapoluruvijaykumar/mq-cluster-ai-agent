import json
from typing import Optional, List
import requests
from requests.auth import HTTPBasicAuth
from .base import BaseMQExecutor, ExecutionResult


class RESTExecutor(BaseMQExecutor):
    """
    Executes commands using the official IBM MQ Administrative REST API.
    Available on IBM MQ 9.0.4+ and Container/Appliance installations.
    """

    def __init__(
        self,
        base_url: str = "https://localhost:9443",
        username: str = "admin",
        password: str = "pass",
        verify_ssl: bool = False
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.username, self.password)
        # IBM MQ Administrative REST API requires CSRF header on POST requests
        self.session.headers.update({
            "Content-Type": "application/json",
            "ibm-mq-rest-csrf-token": "ibm-mq-rest-csrf-token"
        })

    def execute_mqsc(self, qmgr_name: str, mqsc_text: str) -> ExecutionResult:
        """
        Submits MQSC commands to /ibmmq/rest/v2/admin/action/qmgr/<qmgr>/mqsc
        """
        # Split script into individual non-comment commands
        commands = self._parse_mqsc_commands(mqsc_text)
        if not commands:
            return ExecutionResult(
                success=True,
                qmgr=qmgr_name,
                stdout="No executable MQSC commands found in script."
            )

        url = f"{self.base_url}/ibmmq/rest/v2/admin/action/qmgr/{qmgr_name}/mqsc"
        payload = {"commands": commands}

        try:
            response = self.session.post(
                url,
                json=payload,
                verify=self.verify_ssl,
                timeout=20
            )

            if response.status_code == 200:
                data = response.json()
                outputs = []
                all_ok = True

                for item in data.get("commandResponse", []):
                    text_lines = item.get("text", [])
                    completion_code = item.get("completionCode", 0)
                    if completion_code != 0:
                        all_ok = False
                    outputs.append("\n".join(text_lines))

                return ExecutionResult(
                    success=all_ok,
                    qmgr=qmgr_name,
                    stdout="\n---\n".join(outputs),
                    return_code=0 if all_ok else 1,
                    metadata={"response": data}
                )
            else:
                return ExecutionResult(
                    success=False,
                    qmgr=qmgr_name,
                    stderr=f"HTTP {response.status_code}: {response.text}",
                    return_code=response.status_code
                )
        except requests.exceptions.RequestException as e:
            return ExecutionResult(
                success=False,
                qmgr=qmgr_name,
                stderr=f"REST API connection failure: {str(e)}",
                return_code=-1
            )

    def check_health(self, qmgr_name: str) -> ExecutionResult:
        """
        Query QMgr status via GET /ibmmq/rest/v2/admin/qmgr/<qmgr>
        """
        url = f"{self.base_url}/ibmmq/rest/v2/admin/qmgr/{qmgr_name}"
        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=10)
            if response.status_code == 200:
                data = response.json()
                status = data.get("state", "UNKNOWN")
                return ExecutionResult(
                    success=True,
                    qmgr=qmgr_name,
                    stdout=f"Queue Manager {qmgr_name} State: {status}",
                    metadata=data
                )
            return ExecutionResult(
                success=False,
                qmgr=qmgr_name,
                stderr=f"HTTP {response.status_code}: {response.text}",
                return_code=response.status_code
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                qmgr=qmgr_name,
                stderr=str(e),
                return_code=-1
            )

    def _parse_mqsc_commands(self, mqsc_text: str) -> List[str]:
        """
        Merges lines with continuation character '+' and skips comment lines '*'.
        """
        raw_lines = mqsc_text.splitlines()
        commands: List[str] = []
        current_cmd = []

        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("*"):
                continue

            if stripped.endswith("+"):
                current_cmd.append(stripped[:-1].strip())
            else:
                current_cmd.append(stripped)
                commands.append(" ".join(current_cmd))
                current_cmd = []

        if current_cmd:
            commands.append(" ".join(current_cmd))

        return commands

