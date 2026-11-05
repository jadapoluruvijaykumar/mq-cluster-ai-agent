from typing import Dict, List, Optional
from pydantic import BaseModel


class DiagnosticAdvice(BaseModel):
    code_or_symptom: str
    category: str
    cause: str
    remediation_steps: List[str]
    sample_mqsc: Optional[str] = None


class ClusterDiagnostics:
    """
    Expert system for diagnosing IBM MQ Cluster configuration, channel,
    and repository synchronization issues.
    """

    KNOWLEDGE_BASE: Dict[str, DiagnosticAdvice] = {
        "AMQ9448": DiagnosticAdvice(
            code_or_symptom="AMQ9448",
            category="Repository Protocol Error",
            cause="Repository command returned an error or cluster cache is inconsistent.",
            remediation_steps=[
                "Verify both Full Repositories can resolve and ping each other's CONNAME.",
                "Ensure matching cluster name in all CLUSRCVR and CLUSSDR definitions.",
                "Execute REFRESH CLUSTER(cluster_name) REPOS(YES) on affected Partial Repository."
            ],
            sample_mqsc="REFRESH CLUSTER('PAYMENT_CLUS') REPOS(YES)"
        ),
        "AMQ9457": DiagnosticAdvice(
            code_or_symptom="AMQ9457",
            category="Unknown Queue Manager in Repository",
            cause="A repository update was received for a queue manager that this repository does not recognize.",
            remediation_steps=[
                "Check if a Queue Manager was deleted or recreated with a new QMID without cleanly leaving the cluster.",
                "Run RESET CLUSTER(cluster_name) QMNAME(old_qmgr_name) ACTION(FORCEREMOVE) on the Full Repository."
            ],
            sample_mqsc="RESET CLUSTER('PAYMENT_CLUS') QMNAME('OLD_QM') ACTION(FORCEREMOVE)"
        ),
        "AMQ9514": DiagnosticAdvice(
            code_or_symptom="AMQ9514",
            category="Channel Stopped",
            cause="Cluster-Sender or Cluster-Receiver channel transitioned to STOPPED status due to max retries or manual intervention.",
            remediation_steps=[
                "Inspect the Queue Manager error log (AMQERR01.LOG) for underlying network or security error.",
                "Ensure the remote listener is running (DISPLAY LSSTATUS).",
                "Start the channel manually using START CHANNEL."
            ],
            sample_mqsc="START CHANNEL('TO.QM2')"
        ),
        "AMQ9202": DiagnosticAdvice(
            code_or_symptom="AMQ9202",
            category="Network / Connection Refused",
            cause="Cannot connect to remote host CONNAME. Remote listener is stopped or firewall is blocking the port.",
            remediation_steps=[
                "Verify remote listener is started: DISPLAY LISTENER(*) and START LISTENER(...).",
                "Verify network port reachability using test-netconnection / nc / telnet.",
                "Check CONNAME in CLUSRCVR definition of the target queue manager."
            ],
            sample_mqsc="START LISTENER('LISTENER.1414')"
        ),
        "CHANNEL_RETRYING": DiagnosticAdvice(
            code_or_symptom="CHANNEL_RETRYING",
            category="Channel State",
            cause="CLUSSDR channel cannot establish TCP handshake with remote CLUSRCVR.",
            remediation_steps=[
                "Confirm CONNAME format on the target CLUSRCVR is valid (e.g. host(port), not localhost if remote).",
                "Ensure MCAUSER or TLS credentials match if channel authentication (CHLAUTH) is active.",
                "Check CHLAUTH rules on target QMgr: DISPLAY CHLAUTH(*) TYPE(ADDRESSMAP)."
            ],
            sample_mqsc="DISPLAY CHSTATUS('TO.*') ALL"
        ),
        "WORKLOAD_NOT_BALANCING": DiagnosticAdvice(
            code_or_symptom="WORKLOAD_NOT_BALANCING",
            category="Cluster Workload",
            cause="Messages are piling up on one queue manager instead of being distributed across all cluster instances.",
            remediation_steps=[
                "Check DEFBIND on the cluster queue. If set to DEFBIND(FIXED), messages from one connection all go to the same instance.",
                "Change DEFBIND to NOTFIXED: ALTER QLOCAL(QNAME) DEFBIND(NOTFIXED).",
                "Ensure the client application opens the queue with MQOO_BIND_NOT_FIXED."
            ],
            sample_mqsc="ALTER QLOCAL('ORDERS.IN') CLUSTER('MY_CLUS') DEFBIND(NOTFIXED)"
        ),
    }

    @classmethod
    def diagnose(cls, query: str) -> List[DiagnosticAdvice]:
        """
        Matches error codes or symptoms in user query against known cluster issues.
        """
        clean_query = query.upper().replace("-", "_")
        matches = []

        for key, advice in cls.KNOWLEDGE_BASE.items():
            if key in clean_query or any(word in clean_query for word in key.split("_")):
                matches.append(advice)

        # Keyword matching
        if not matches:
            if "RETRY" in clean_query or "RETRYING" in clean_query:
                matches.append(cls.KNOWLEDGE_BASE["CHANNEL_RETRYING"])
            elif "BALANCE" in clean_query or "WORKLOAD" in clean_query:
                matches.append(cls.KNOWLEDGE_BASE["WORKLOAD_NOT_BALANCING"])
            elif "REFRESH" in clean_query or "SYNC" in clean_query or "CACHE" in clean_query:
                matches.append(cls.KNOWLEDGE_BASE["AMQ9448"])

        return matches
