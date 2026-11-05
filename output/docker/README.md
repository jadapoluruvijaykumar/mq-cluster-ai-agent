# IBM MQ Cluster Local Docker Lab: PAYMENT_CLUS

## Cluster Overview
- **Cluster Name**: `PAYMENT_CLUS`
- **Full Repositories**: `QM1, QM2`
- **Partial Repositories**: `QM3`
- **Cluster Queues**: `PAYMENT.REQ`

## Quickstart

### 1. Start the cluster:
```bash
docker compose up -d
```

### 2. Verify cluster status:
Check cluster queue managers from any node:
```bash
docker exec -it qm1 runmqsc QM1
# Inside runmqsc:
DISPLAY CLUSQMGR(*)
DISPLAY CHSTATUS(TO.*)
```

### 3. Web Console / REST API:
Access the IBM MQ Console at:
- QM1: `https://localhost:9443/ibmmq/console`
  - User: `admin`
  - Password: `pass`

### 4. Stop the cluster:
```bash
docker compose down
```
