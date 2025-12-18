#!/bin/bash

# =============================================================================
# CDC Pipeline Setup Script
# =============================================================================
# This script sets up the complete CDC (Change Data Capture) pipeline:
# 1. Enable PostgreSQL logical replication
# 2. Create required secrets
# 3. Deploy Kafka cluster with Strimzi
# 4. Deploy Debezium Kafka Connect
# 5. Create C2C CDC connector
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=========================================="
echo "🚀 CDC Pipeline Setup"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Step 1: Check Prerequisites
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Step 1: Checking prerequisites...${NC}"

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

# Check helm
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ helm not found. Please install helm first.${NC}"
    exit 1
fi

# Check Strimzi operator
if ! kubectl get pods -n operators | grep -q strimzi; then
    echo -e "${RED}❌ Strimzi operator not found in operators namespace.${NC}"
    echo "Please install Strimzi operator first."
    exit 1
fi
echo -e "${GREEN}✅ Strimzi operator is running${NC}"

# Check PostgreSQL
if ! kubectl get pods -n orchestration | grep -q airflow-postgresql; then
    echo -e "${RED}❌ PostgreSQL not found in orchestration namespace.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ PostgreSQL is running${NC}"

# -----------------------------------------------------------------------------
# Step 2: Enable PostgreSQL Logical Replication
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Step 2: Enabling PostgreSQL logical replication...${NC}"

PGPASSWORD=$(kubectl get secret -n orchestration airflow-postgresql -o jsonpath='{.data.postgres-password}' | base64 -d)

# Check current wal_level
WAL_LEVEL=$(kubectl exec -n orchestration airflow-postgresql-0 -- bash -c "PGPASSWORD='$PGPASSWORD' psql -U postgres -t -c 'SHOW wal_level;'" | tr -d ' ')

if [ "$WAL_LEVEL" = "logical" ]; then
    echo -e "${GREEN}✅ wal_level is already set to logical${NC}"
else
    echo -e "${YELLOW}⚠️  Current wal_level: $WAL_LEVEL (needs to be 'logical')${NC}"
    echo -e "${YELLOW}Updating PostgreSQL configuration...${NC}"
    
    # Update postgresql.conf
    kubectl exec -n orchestration airflow-postgresql-0 -- bash -c "
        PGPASSWORD='$PGPASSWORD' psql -U postgres -c \"ALTER SYSTEM SET wal_level = 'logical';\"
        PGPASSWORD='$PGPASSWORD' psql -U postgres -c \"ALTER SYSTEM SET max_replication_slots = 10;\"
        PGPASSWORD='$PGPASSWORD' psql -U postgres -c \"ALTER SYSTEM SET max_wal_senders = 10;\"
    "
    
    echo -e "${YELLOW}⚠️  PostgreSQL needs to be restarted for changes to take effect.${NC}"
    echo -e "${YELLOW}   Run: kubectl rollout restart statefulset/airflow-postgresql -n orchestration${NC}"
    echo -e "${YELLOW}   Then run this script again.${NC}"
    
    read -p "Would you like to restart PostgreSQL now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl rollout restart statefulset/airflow-postgresql -n orchestration
        echo "Waiting for PostgreSQL to restart (this may take 1-2 minutes)..."
        kubectl rollout status statefulset/airflow-postgresql -n orchestration --timeout=300s
        sleep 10
    else
        echo "Please restart PostgreSQL manually and run this script again."
        exit 0
    fi
fi

# Verify wal_level after restart
WAL_LEVEL=$(kubectl exec -n orchestration airflow-postgresql-0 -- bash -c "PGPASSWORD='$PGPASSWORD' psql -U postgres -t -c 'SHOW wal_level;'" | tr -d ' ')
if [ "$WAL_LEVEL" != "logical" ]; then
    echo -e "${RED}❌ wal_level is still not 'logical'. Please check PostgreSQL configuration.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ wal_level is set to logical${NC}"

# -----------------------------------------------------------------------------
# Step 3: Create C2C database and table if not exists
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Step 3: Setting up c2c_trade database...${NC}"

kubectl exec -n orchestration airflow-postgresql-0 -- bash -c "
    PGPASSWORD='$PGPASSWORD' psql -U postgres <<EOF
    -- Create database if not exists
    SELECT 'CREATE DATABASE c2c_trade' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'c2c_trade')\gexec
EOF
" 2>/dev/null || true

# Connect to c2c_trade and create schema/table
kubectl exec -n orchestration airflow-postgresql-0 -- bash -c "
    PGPASSWORD='$PGPASSWORD' psql -U postgres -d c2c_trade <<EOF
    -- Create schema
    CREATE SCHEMA IF NOT EXISTS c2c;
    
    -- Create table
    CREATE TABLE IF NOT EXISTS c2c.trades (
        order_number TEXT PRIMARY KEY,
        adv_no TEXT,
        trade_type TEXT CHECK (trade_type IN ('BUY','SELL')),
        asset VARCHAR(16),
        fiat VARCHAR(16),
        fiat_symbol VARCHAR(16),
        amount NUMERIC(38, 8) CHECK (amount >= 0),
        total_price NUMERIC(38, 8) CHECK (total_price >= 0),
        unit_price NUMERIC(38, 8) CHECK (unit_price >= 0),
        order_status TEXT,
        create_time BIGINT,
        commission NUMERIC(38, 8) CHECK (commission >= 0),
        counter_part_nick_name TEXT,
        advertisement_role TEXT
    );
    
    -- Create publication for CDC
    DROP PUBLICATION IF EXISTS c2c_publication;
    CREATE PUBLICATION c2c_publication FOR TABLE c2c.trades;
    
    -- Grant permissions
    GRANT USAGE ON SCHEMA c2c TO postgres;
    GRANT SELECT ON ALL TABLES IN SCHEMA c2c TO postgres;
    ALTER DEFAULT PRIVILEGES IN SCHEMA c2c GRANT SELECT ON TABLES TO postgres;
EOF
" 2>/dev/null

echo -e "${GREEN}✅ c2c_trade database and c2c.trades table created${NC}"

# -----------------------------------------------------------------------------
# Step 4: Create Kubernetes Secrets for Debezium
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Step 4: Creating Kubernetes secrets...${NC}"

# Create postgres-credentials secret for Debezium
kubectl create secret generic postgres-credentials -n infrastructure \
    --from-literal=hostname=airflow-postgresql.orchestration.svc.cluster.local \
    --from-literal=port=5432 \
    --from-literal=user=postgres \
    --from-literal=password="$PGPASSWORD" \
    --from-literal=dbname=c2c_trade \
    --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}✅ postgres-credentials secret created/updated${NC}"

# Create minio-credentials secret (if MinIO is used for S3 sink)
MINIO_ACCESS_KEY=$(kubectl get secret -n storage minio-tenant-user-1 -o jsonpath='{.data.CONSOLE_ACCESS_KEY}' 2>/dev/null | base64 -d || echo "minio")
MINIO_SECRET_KEY=$(kubectl get secret -n storage minio-tenant-user-1 -o jsonpath='{.data.CONSOLE_SECRET_KEY}' 2>/dev/null | base64 -d || echo "minio123")

kubectl create secret generic minio-credentials -n infrastructure \
    --from-literal=access-key="$MINIO_ACCESS_KEY" \
    --from-literal=secret-key="$MINIO_SECRET_KEY" \
    --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}✅ minio-credentials secret created/updated${NC}"

# -----------------------------------------------------------------------------
# Step 5: Deploy Kafka Cluster with Strimzi
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Step 5: Deploying Kafka cluster...${NC}"

cd "$SCRIPT_DIR"
helm upgrade --install strimzi-kafka . -n infrastructure

echo "Waiting for Kafka to be ready (this may take 3-5 minutes)..."

# Wait for Kafka pods
sleep 30
kubectl wait --for=condition=Ready pod -l strimzi.io/name=kafka-kafka -n infrastructure --timeout=300s 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Kafka pods are still starting. Please wait...${NC}"
    echo "You can check status with: kubectl get pods -n infrastructure -w"
}

echo -e "${GREEN}✅ Kafka cluster deployed${NC}"

# -----------------------------------------------------------------------------
# Step 6: Wait for Kafka Connect
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Step 6: Waiting for Kafka Connect...${NC}"

kubectl wait --for=condition=Ready pod -l strimzi.io/name=debezium-connect-cluster-connect -n infrastructure --timeout=300s 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Kafka Connect is still starting. Please wait...${NC}"
}

echo -e "${GREEN}✅ Kafka Connect is ready${NC}"

# -----------------------------------------------------------------------------
# Step 7: Deploy C2C CDC Connector
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Step 7: Deploying C2C CDC Connector...${NC}"

kubectl apply -f "$SCRIPT_DIR/c2c-connector.yaml"

echo -e "${GREEN}✅ C2C CDC Connector deployed${NC}"

# -----------------------------------------------------------------------------
# Step 8: Verify Setup
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Step 8: Verifying setup...${NC}"

echo ""
echo "Kafka Pods:"
kubectl get pods -n infrastructure -l strimzi.io/cluster=kafka

echo ""
echo "Kafka Connect Pods:"
kubectl get pods -n infrastructure -l strimzi.io/cluster=debezium-connect-cluster

echo ""
echo "Kafka Connectors:"
kubectl get kafkaconnectors -n infrastructure

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=========================================="
echo -e "${GREEN}🎉 CDC Pipeline Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "📊 Architecture Overview:"
echo "   PostgreSQL (orchestration) --> Debezium --> Kafka (infrastructure)"
echo "                                      |"
echo "                                      v"
echo "                              Topic: c2c_cdc.c2c.trades"
echo ""
echo "📝 Useful commands:"
echo "   - Check Kafka pods:     kubectl get pods -n infrastructure"
echo "   - Check connector:      kubectl get kafkaconnectors -n infrastructure"
echo "   - Describe connector:   kubectl describe kafkaconnector c2c-trades-connector -n infrastructure"
echo "   - View Kafka UI:        kubectl port-forward svc/kafka-ui-svc 8080:8080 -n infrastructure"
echo "   - Check connector logs: kubectl logs -n infrastructure \$(kubectl get pods -n infrastructure -l strimzi.io/name=debezium-connect-cluster-connect -o name | head -1)"
echo ""

