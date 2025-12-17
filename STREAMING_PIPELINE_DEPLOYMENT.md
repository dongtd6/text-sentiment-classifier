# C2C Complete Streaming Pipeline - Deployment Guide

Complete guide for deploying the end-to-end C2C streaming pipeline with API ingestion, CDC, and Telegram notifications.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Binance C2C API                              │
└────────────────────────┬────────────────────────────────────────┘
                         │ (1) API Fetch
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│     Airflow DAG: c2c_complete_streaming_pipeline                │
│     • Triggers: @hourly                                         │
│     • Runs: streaming-app Docker image                          │
└────────────────────────┬────────────────────────────────────────┘
                         │ (2) Insert Data
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│          PostgreSQL Database (storage namespace)                │
│          Table: c2c.trades                                      │
│          • Logical replication enabled                          │
│          • Publication: c2c_publication                         │
└────────────────────────┬────────────────────────────────────────┘
                         │ (3) CDC Stream
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│          Debezium PostgreSQL Connector                          │
│          • Connector: c2c-trades-connector                      │
│          • Slot: c2c_trades_slot                                │
└────────────────────────┬────────────────────────────────────────┘
                         │ (4) Kafka Messages
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│            Kafka Cluster (infrastructure namespace)             │
│            Topic: c2c_cdc.c2c.trades                            │
└────────────────────────┬────────────────────────────────────────┘
                         │ (5) Consume & Process
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│          Flink Job: flink-c2c-telegram-job                      │
│          • Processes CDC events                                 │
│          • Formats notifications                                │
└────────────────────────┬────────────────────────────────────────┘
                         │ (6) Send Alerts
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Telegram Bot API                                │
│                 • Real-time notifications                       │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. Kubernetes Cluster
- Running Kubernetes cluster (GKE, EKS, or local)
- `kubectl` configured and authenticated
- Namespaces created:
  - `storage` (PostgreSQL)
  - `orchestration` (Airflow)
  - `infrastructure` (Kafka, Flink)

### 2. Required Operators
```bash
# Strimzi Kafka Operator
kubectl create namespace infrastructure
kubectl apply -f https://strimzi.io/install/latest?namespace=infrastructure

# Flink Kubernetes Operator
helm repo add flink-operator-repo https://downloads.apache.org/flink/flink-kubernetes-operator-1.7.0/
helm install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator \
  --namespace infrastructure
```

### 3. Credentials
- Binance API key and secret
- PostgreSQL admin password
- Telegram bot token and chat ID
- GCP service account (for Artifact Registry)

## Step-by-Step Deployment

### Phase 1: Setup PostgreSQL with CDC

#### 1.1 Enable Logical Replication

```bash
# Port forward to PostgreSQL
kubectl port-forward svc/postgresql 5432:5432 -n storage

# In another terminal, run the setup script
cd helm-charts/postgresql/initdata
python3 setup_cdc_for_c2c.py
```

This script will:
- ✅ Create `c2c` schema and `trades` table
- ✅ Configure PostgreSQL for logical replication
- ✅ Create publication `c2c_publication`
- ✅ Grant replication privileges

#### 1.2 Restart PostgreSQL (if needed)

```bash
kubectl exec -it postgresql-0 -n storage -- pg_ctl restart
```

#### 1.3 Verify CDC Setup

```bash
python3 setup_cdc_for_c2c.py  # Run again to verify
```

Look for:
- ✅ `wal_level = logical`
- ✅ Publication exists
- ✅ User has REPLICATION privilege

### Phase 2: Deploy Kafka and CDC Connector

#### 2.1 Deploy Kafka Cluster

```bash
cd helm-charts/strimzi-kafka-operator
helm install kafka-cluster . -n infrastructure
```

Wait for Kafka to be ready:
```bash
kubectl wait kafka/kafka --for=condition=Ready --timeout=300s -n infrastructure
```

#### 2.2 Deploy Kafka Connect with Debezium

Already included in the Helm chart. Verify:
```bash
kubectl get kafkaconnect -n infrastructure
```

#### 2.3 Deploy CDC Connector

```bash
kubectl apply -f helm-charts/strimzi-kafka-operator/c2c-connector.yaml
```

#### 2.4 Verify CDC Connector

```bash
# Check connector status
kubectl get kafkaconnector c2c-trades-connector -n infrastructure

# View connector details
kubectl get kafkaconnector c2c-trades-connector -n infrastructure -o yaml

# Check Kafka topic created
kubectl exec -it kafka-kafka-0 -n infrastructure -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --list | grep c2c
```

Expected topic: `c2c_cdc.c2c.trades`

### Phase 3: Build and Deploy Docker Images

#### 3.1 Build Streaming App (for data ingestion)

**Option A: Using Jenkins (Recommended)**

```bash
# Push changes to trigger Jenkins
git add dockerfiles/streaming-processing/
git commit -m "Update streaming processing"
git push origin airflow
```

Jenkins will automatically:
1. Build `streaming-app:latest`
2. Push to Google Artifact Registry
3. Tag as `asia-southeast1-docker.pkg.dev/${PROJECT}/bnb-c2c-images/streaming-app:latest`

**Option B: Manual Build**

```bash
cd /path/to/Sentiment-Classifier-ML-System-on-K8S

# Build
docker build -f dockerfiles/streaming-processing/Dockerfile -t streaming-app:latest .

# Tag and push
docker tag streaming-app:latest asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/streaming-app:latest
docker push asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/streaming-app:latest
```

#### 3.2 Build Flink Image (for Telegram notifications)

```bash
cd flink-sentiment

# Update version in note.txt
export TAG=v1.40

# Build and push
docker build -t asia-southeast1-docker.pkg.dev/dongtd2/flink/flink-sentiment:${TAG} .
docker push asia-southeast1-docker.pkg.dev/dongtd2/flink/flink-sentiment:${TAG}
```

### Phase 4: Create Kubernetes Secrets

#### 4.1 Airflow Secrets (for API credentials)

```bash
kubectl create secret generic airflow-producer-secret \
  --from-literal=API_KEY=your_binance_api_key \
  --from-literal=API_SECRET=your_binance_api_secret \
  -n orchestration
```

#### 4.2 PostgreSQL Secret (if not exists)

```bash
kubectl create secret generic postgresql \
  --from-literal=postgres-password=your_postgres_password \
  -n storage
```

#### 4.3 Telegram Secret

```bash
kubectl create secret generic telegram-secrets \
  --from-literal=bot-token=your_telegram_bot_token \
  --from-literal=chat-id=your_telegram_chat_id \
  -n infrastructure
```

### Phase 5: Deploy Flink Job

```bash
# Apply Flink deployment
kubectl apply -f helm-charts/flink-kubernetes-operator/flink-c2c-telegram-job.yaml

# Check deployment status
kubectl get flinkdeployment -n infrastructure

# View logs
kubectl logs -n infrastructure deployment/flink-c2c-telegram-job-jobmanager -f
```

Wait for status to show `RUNNING`.

### Phase 6: Deploy Airflow DAG

#### 6.1 Copy DAG to Airflow

```bash
# Find Airflow scheduler pod
AIRFLOW_POD=$(kubectl get pods -n orchestration -l component=scheduler -o jsonpath='{.items[0].metadata.name}')

# Copy DAG file
kubectl cp dags/c2c_complete_streaming_dag.py ${AIRFLOW_POD}:/opt/airflow/dags/ -n orchestration
```

**Or if using Git-sync:**

```bash
git add dags/c2c_complete_streaming_dag.py
git commit -m "Add complete streaming pipeline DAG"
git push origin airflow
```

#### 6.2 Verify DAG in Airflow UI

```bash
# Port forward to Airflow
kubectl port-forward svc/airflow-webserver 8080:8080 -n orchestration
```

Open: http://localhost:8080
- Login with credentials
- Find DAG: `c2c_complete_streaming_pipeline`
- Enable the DAG

### Phase 7: Test the Pipeline

#### 7.1 Trigger DAG Manually

In Airflow UI:
1. Click on `c2c_complete_streaming_pipeline`
2. Click "Trigger DAG" button
3. Monitor task execution

#### 7.2 Monitor Components

**PostgreSQL:**
```bash
kubectl port-forward svc/postgresql 5432:5432 -n storage
psql -h localhost -U pgadmin -d postgres

# Check data
SELECT COUNT(*) FROM c2c.trades;
SELECT * FROM c2c.trades ORDER BY create_time_ms DESC LIMIT 5;
```

**Kafka Topic:**
```bash
kubectl exec -it kafka-kafka-0 -n infrastructure -- \
  bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic c2c_cdc.c2c.trades \
  --from-beginning
```

**Flink Job:**
```bash
kubectl logs -n infrastructure deployment/flink-c2c-telegram-job-taskmanager -f
```

**Telegram:**
Check your Telegram bot/channel for notifications!

#### 7.3 Insert Test Data

```bash
# Insert a test trade
kubectl exec -it postgresql-0 -n storage -- psql -U pgadmin -d postgres

INSERT INTO c2c.trades (
    order_number, adv_no, trade_type, asset, fiat, fiat_symbol,
    amount, total_price, unit_price, order_status, create_time_ms,
    commission, counter_part_nick_name, advertisement_role
) VALUES (
    'TEST-' || NOW()::TEXT,
    'ADV-12345',
    'BUY',
    'BTC',
    'VND',
    '₫',
    0.001,
    25000000,
    25000000000,
    'COMPLETED',
    EXTRACT(EPOCH FROM NOW())::BIGINT * 1000,
    0.00001,
    'TestUser',
    'BUYER'
);
```

You should receive a Telegram notification within seconds!

## Monitoring and Troubleshooting

### Check System Health

```bash
# Check all components
kubectl get pods -n storage
kubectl get pods -n orchestration
kubectl get pods -n infrastructure

# Check Kafka Connect
kubectl get kafkaconnect -n infrastructure
kubectl get kafkaconnector -n infrastructure

# Check Flink
kubectl get flinkdeployment -n infrastructure
```

### Common Issues

#### Issue 1: CDC Connector Not Starting

**Symptoms:**
- Connector shows `FAILED` status
- No CDC topic created

**Solution:**
```bash
# Check connector logs
kubectl logs -n infrastructure deployment/debezium-connect-cluster-connect -f

# Verify PostgreSQL replication settings
kubectl exec -it postgresql-0 -n storage -- psql -U pgadmin -d postgres -c "SHOW wal_level;"

# Should return: logical
# If not, restart PostgreSQL after running setup_cdc_for_c2c.py
```

#### Issue 2: Flink Job Not Consuming

**Symptoms:**
- Flink job running but no logs
- No Telegram notifications

**Solution:**
```bash
# Check Flink logs
kubectl logs -n infrastructure deployment/flink-c2c-telegram-job-taskmanager -f

# Verify Kafka topic has messages
kubectl exec -it kafka-kafka-0 -n infrastructure -- \
  bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic c2c_cdc.c2c.trades \
  --from-beginning \
  --max-messages 10

# Check Telegram credentials
kubectl get secret telegram-secrets -n infrastructure -o yaml
```

#### Issue 3: DAG Failing

**Symptoms:**
- Airflow task shows red (failed)
- Data not inserted

**Solution:**
```bash
# Check DAG logs in Airflow UI
# Or check pod logs
kubectl logs -n orchestration <failed-pod-name>

# Verify secrets exist
kubectl get secret airflow-producer-secret -n orchestration
kubectl get secret postgresql -n storage

# Test manually
kubectl run -it --rm test-streaming --image=asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/streaming-app:latest -n orchestration -- /bin/bash
```

## Scaling and Optimization

### Scale Kafka

```bash
# Edit Kafka replicas
kubectl edit kafka kafka -n infrastructure

# Change spec.kafka.replicas to desired number
```

### Scale Flink

Edit `flink-c2c-telegram-job.yaml`:
```yaml
spec:
  flinkConfiguration:
    parallelism.default: 2  # Increase parallelism
  taskManager:
    replicas: 2  # More task managers
```

Apply changes:
```bash
kubectl apply -f helm-charts/flink-kubernetes-operator/flink-c2c-telegram-job.yaml
```

### Adjust DAG Schedule

Edit `c2c_complete_streaming_dag.py`:
```python
schedule='@hourly',  # Change to '@daily', '*/30 * * * *', etc.
```

## Maintenance

### Update Docker Images

**Via Jenkins (Automatic):**
```bash
git add dockerfiles/streaming-processing/
git commit -m "Update streaming logic"
git push origin airflow
```

**Manual:**
```bash
# Rebuild and push
docker build -f dockerfiles/streaming-processing/Dockerfile -t streaming-app:latest .
docker push asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/streaming-app:latest

# Airflow will pull new image on next run (image_pull_policy='Always')
```

### Backup and Recovery

**PostgreSQL Backup:**
```bash
kubectl exec -it postgresql-0 -n storage -- \
  pg_dump -U pgadmin -d postgres -t c2c.trades > c2c_trades_backup.sql
```

**Kafka Topic Backup:**
Use Kafka tools or enable topic replication.

### Clean Up

```bash
# Delete Flink job
kubectl delete flinkdeployment flink-c2c-telegram-job -n infrastructure

# Delete CDC connector
kubectl delete kafkaconnector c2c-trades-connector -n infrastructure

# Pause DAG in Airflow UI
```

## Performance Metrics

Monitor these key metrics:

1. **Data Ingestion Rate**: Records/hour inserted into PostgreSQL
2. **CDC Lag**: Time between DB insert and Kafka message
3. **Flink Processing**: Messages/second processed
4. **Telegram Delivery**: Notification latency

Access metrics via:
- Kafka UI: `kubectl port-forward svc/kafka-ui-svc 8080:8080 -n infrastructure`
- Flink Dashboard: `kubectl port-forward svc/flink-c2c-telegram-job 8081:8081 -n infrastructure`

## Security Best Practices

✅ Use Kubernetes Secrets for all credentials
✅ Enable TLS for Kafka (production)
✅ Use RBAC for service accounts
✅ Rotate API keys regularly
✅ Monitor for anomalies

## Next Steps

1. **Add Data Quality Checks**: Validate data before insertion
2. **Implement Alerting**: Set up alerts for pipeline failures
3. **Create Dashboards**: Visualize metrics in Grafana
4. **Add More Notification Channels**: Slack, Email, etc.
5. **Implement Data Archival**: Move old data to cold storage

## Support

For issues:
1. Check logs in Airflow UI
2. Review Kubernetes pod logs
3. Verify all secrets are configured
4. Test each component independently

Happy Streaming! 🚀

