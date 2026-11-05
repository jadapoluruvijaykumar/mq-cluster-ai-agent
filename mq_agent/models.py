from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, field_validator


class QMgrRole(str, Enum):
    FULL_REPOSITORY = "FR"
    PARTIAL_REPOSITORY = "PR"


class ChannelType(str, Enum):
    CLUSRCVR = "CLUSRCVR"
    CLUSSDR = "CLUSSDR"


class ExecutionMode(str, Enum):
    SIMULATION = "simulation"
    LOCAL_RUNMQSC = "local_runmqsc"
    REST_API = "rest_api"
    DOCKER = "docker"


class ChannelDef(BaseModel):
    name: str
    channel_type: ChannelType
    conname: str
    cluster: str
    target_qmgr: Optional[str] = None
    descr: Optional[str] = None


class QMgrNode(BaseModel):
    name: str = Field(..., description="Queue Manager name (up to 48 characters)")
    role: QMgrRole = Field(QMgrRole.PARTIAL_REPOSITORY, description="Full Repository (FR) or Partial Repository (PR)")
    host: str = Field("localhost", description="Hostname or IP address for CONNAME")
    port: int = Field(1414, description="Listener TCP port")
    rest_port: int = Field(9443, description="IBM MQ Administrative REST port")
    listener_name: Optional[str] = None
    clusrcvr_channel_name: Optional[str] = None
    cluster_sender_targets: List[str] = Field(default_factory=list, description="Target QMgr names for CLUSSDR channels")
    queues: List[str] = Field(default_factory=list, description="Queues hosted by this queue manager")

    @field_validator("name")
    def validate_name_length(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean:
            raise ValueError("Queue manager name cannot be empty")
        if len(clean) > 48:
            raise ValueError("Queue manager name cannot exceed 48 characters")
        return clean

    @property
    def computed_listener_name(self) -> str:
        return self.listener_name or f"LISTENER.{self.port}"

    @property
    def computed_clusrcvr_name(self) -> str:
        if self.clusrcvr_channel_name:
            return self.clusrcvr_channel_name.upper()
        # Default IBM MQ convention: TO.<QMGR_NAME>
        return f"TO.{self.name}"

    @property
    def conname(self) -> str:
        return f"{self.host}({self.port})"


class ClusterQueueDef(BaseModel):
    name: str
    cluster: str
    defbind: str = Field("NOTFIXED", description="NOTFIXED is best practice for cluster workload balancing")
    descr: Optional[str] = None


class ClusterTopology(BaseModel):
    cluster_name: str = Field(..., description="Cluster name (up to 48 characters)")
    description: Optional[str] = Field(None, description="Description of the cluster")
    nodes: Dict[str, QMgrNode] = Field(default_factory=dict)
    cluster_queues: List[str] = Field(default_factory=list)

    @field_validator("cluster_name")
    def validate_cluster_name(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean:
            raise ValueError("Cluster name cannot be empty")
        if len(clean) > 48:
            raise ValueError("Cluster name cannot exceed 48 characters")
        return clean

    @property
    def full_repositories(self) -> List[QMgrNode]:
        return [node for node in self.nodes.values() if node.role == QMgrRole.FULL_REPOSITORY]

    @property
    def partial_repositories(self) -> List[QMgrNode]:
        return [node for node in self.nodes.values() if node.role == QMgrRole.PARTIAL_REPOSITORY]


class ValidationResult(BaseModel):
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
