#!/bin/bash
# This script configures PostgreSQL CDC settings from outside the pod
# Run this script from your local machine after PostgreSQL is installed
# 
# Usage: bash setup_cdc_postgres_superuser.sh

echo "🔐 Running CDC setup with PostgreSQL superuser privileges..."

# PostgreSQL root password from auth-values.yaml
POSTGRES_ROOT_PASSWORD="rootpw"
NAMESPACE="storage"
POD_NAME="postgresql-0"

echo ""
echo "📋 Step 1: Configure PostgreSQL for logical replication..."
kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
PGPASSWORD=$POSTGRES_ROOT_PASSWORD psql -U postgres -d crm_db -c 'ALTER SYSTEM SET wal_level = logical;'
"
echo "   ✅ wal_level = logical"

kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
PGPASSWORD=$POSTGRES_ROOT_PASSWORD psql -U postgres -d crm_db -c 'ALTER SYSTEM SET max_replication_slots = 4;'
"
echo "   ✅ max_replication_slots = 4"

kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
PGPASSWORD=$POSTGRES_ROOT_PASSWORD psql -U postgres -d crm_db -c 'ALTER SYSTEM SET max_wal_senders = 4;'
"
echo "   ✅ max_wal_senders = 4"

echo ""
echo "🔐 Step 2: Grant replication privilege to pgadmin..."
kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
PGPASSWORD=$POSTGRES_ROOT_PASSWORD psql -U postgres -d crm_db -c 'ALTER ROLE pgadmin WITH REPLICATION;'
"
echo "   ✅ pgadmin now has REPLICATION privilege"

echo ""
echo "======================================================================="
echo "✅ CONFIGURATION COMPLETE!"
echo "======================================================================="
echo ""
echo "⚠️  IMPORTANT: PostgreSQL needs to be restarted to apply changes"
echo ""
echo "Next steps:"
echo "   1. Restart PostgreSQL:"
echo "      kubectl rollout restart statefulset postgresql -n storage"
echo ""
echo "   2. Wait for it to be ready:"
echo "      kubectl wait --for=condition=ready pod/postgresql-0 -n storage --timeout=120s"
echo ""
echo "   3. Verify configuration:"
echo "      python3 setup_cdc_for_c2c.py"
echo ""
echo "   4. Deploy Debezium connector:"
echo "      kubectl apply -f ../strimzi-kafka-operator/c2c-connector.yaml"
echo ""

