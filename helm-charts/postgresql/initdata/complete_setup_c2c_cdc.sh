#!/bin/bash
# Complete setup script for c2c CDC configuration
# Run this after PostgreSQL is freshly installed
#
# Usage: bash complete_setup_c2c_cdc.sh

set -e  # Exit on any error

echo "════════════════════════════════════════════════════════════════"
echo "  Complete C2C CDC Setup Script"
echo "  This will set up c2c schema and CDC configuration"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Configuration
NAMESPACE="storage"
POD_NAME="postgresql-0"
POSTGRES_ROOT_PASSWORD="rootpw"  # From auth-values.yaml
PGADMIN_PASSWORD="pw123"         # From auth-values.yaml

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo "ℹ️  $1"; }

# Check if PostgreSQL is running
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 1: Checking PostgreSQL status..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if kubectl get pod $POD_NAME -n $NAMESPACE &> /dev/null; then
    print_success "PostgreSQL pod found"
    kubectl wait --for=condition=ready pod/$POD_NAME -n $NAMESPACE --timeout=30s
    print_success "PostgreSQL is ready"
else
    print_error "PostgreSQL pod not found. Please install PostgreSQL first:"
    echo "  helm upgrade --install postgresql ./helm-charts/postgresql -f ./helm-charts/postgresql/auth-values.yaml --namespace storage"
    exit 1
fi

# Step 2: Create c2c schema and table
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 2: Creating c2c schema and table..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_info "Starting port-forward to PostgreSQL..."
kubectl port-forward svc/postgresql 5432:5432 -n $NAMESPACE > /dev/null 2>&1 &
PORT_FORWARD_PID=$!
sleep 3

print_info "Running c2c table creation script..."
python3 c2c_table_create.py
if [ $? -eq 0 ]; then
    print_success "c2c schema and table created"
else
    print_error "Failed to create c2c schema/table"
    kill $PORT_FORWARD_PID 2>/dev/null
    exit 1
fi

# Step 3: Configure PostgreSQL for CDC
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 3: Configuring PostgreSQL for CDC (superuser commands)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
PGPASSWORD=$POSTGRES_ROOT_PASSWORD psql -U postgres -d crm_db -c 'ALTER SYSTEM SET wal_level = logical;'
" > /dev/null 2>&1
print_success "wal_level = logical"

kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
PGPASSWORD=$POSTGRES_ROOT_PASSWORD psql -U postgres -d crm_db -c 'ALTER SYSTEM SET max_replication_slots = 4;'
" > /dev/null 2>&1
print_success "max_replication_slots = 4"

kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
PGPASSWORD=$POSTGRES_ROOT_PASSWORD psql -U postgres -d crm_db -c 'ALTER SYSTEM SET max_wal_senders = 4;'
" > /dev/null 2>&1
print_success "max_wal_senders = 4"

kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
PGPASSWORD=$POSTGRES_ROOT_PASSWORD psql -U postgres -d crm_db -c 'ALTER ROLE pgadmin WITH REPLICATION;'
" > /dev/null 2>&1
print_success "pgadmin granted REPLICATION privilege"

# Step 4: Create publication
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 4: Creating CDC publication..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 setup_cdc_for_c2c.py > /dev/null 2>&1
print_success "Publication c2c_publication created"

# Stop port-forward
kill $PORT_FORWARD_PID 2>/dev/null
sleep 1

# Step 5: Restart PostgreSQL
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 5: Restarting PostgreSQL to apply changes..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl rollout restart statefulset postgresql -n $NAMESPACE > /dev/null 2>&1
print_info "PostgreSQL restart initiated..."
sleep 5
kubectl wait --for=condition=ready pod/$POD_NAME -n $NAMESPACE --timeout=120s > /dev/null 2>&1
print_success "PostgreSQL restarted and ready"

# Step 6: Restart port-forward and verify
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 6: Verifying CDC configuration..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl port-forward svc/postgresql 5432:5432 -n $NAMESPACE > /dev/null 2>&1 &
PORT_FORWARD_PID=$!
sleep 5

echo ""
python3 setup_cdc_for_c2c.py
VERIFY_RESULT=$?

# Keep port-forward running
if [ $VERIFY_RESULT -eq 0 ]; then
    print_success "CDC configuration verified!"
else
    print_warning "Verification had some warnings, but setup is complete"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ SETUP COMPLETE!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Current Status:"
echo "   • c2c schema: Created"
echo "   • c2c.trades table: Created"
echo "   • WAL level: logical"
echo "   • Replication: Enabled for pgadmin"
echo "   • Publication: c2c_publication"
echo "   • Port forward: Active on localhost:5432 (PID: $PORT_FORWARD_PID)"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "   1. Insert some dummy data:"
echo "      python3 c2c_insert_dummy.py"
echo "      # or"
echo "      python3 c2c_insert_multiple_dummy.py"
echo ""
echo "   2. Deploy Debezium Kafka connector:"
echo "      kubectl apply -f ../strimzi-kafka-operator/c2c-connector.yaml"
echo ""
echo "   3. Monitor Kafka topic:"
echo "      kubectl exec -it kafka-cluster-kafka-0 -n infrastructure -- \\"
echo "        bin/kafka-console-consumer.sh \\"
echo "        --bootstrap-server localhost:9092 \\"
echo "        --topic c2c-cdc.c2c.trades \\"
echo "        --from-beginning"
echo ""
echo "   4. Connect via DBeaver:"
echo "      Host: localhost"
echo "      Port: 5432"
echo "      Database: crm_db"
echo "      Username: pgadmin"
echo "      Password: pw123"
echo ""
echo "💡 TIP: Keep the port-forward running or restart it when needed:"
echo "   kubectl port-forward svc/postgresql 5432:5432 -n storage"
echo ""
echo "════════════════════════════════════════════════════════════════"

