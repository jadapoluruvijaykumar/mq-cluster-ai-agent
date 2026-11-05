from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ExecutionResult(BaseModel):
    success: bool
    qmgr: str
    command_type: str = "MQSC"
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseMQExecutor(ABC):
    """
    Abstract interface for executing MQSC commands and interacting with IBM MQ.
    """

    @abstractmethod
    def execute_mqsc(self, qmgr_name: str, mqsc_text: str) -> ExecutionResult:
        """
        Executes raw MQSC text against the specified queue manager.
        """
        pass

    @abstractmethod
    def check_health(self, qmgr_name: str) -> ExecutionResult:
        """
        Checks operational status of the specified queue manager.
        """
        pass

