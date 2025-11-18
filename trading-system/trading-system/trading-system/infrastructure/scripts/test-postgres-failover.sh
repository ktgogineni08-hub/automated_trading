#!/bin/bash
# PostgreSQL Failover Test Script
# This script tests automatic failover from primary to replica

set -e

NAMESPACE="trading-system-prod"
PRIMARY_POD="postgres-primary-0"
REPLICA_POD="postgres-replica-0"
TEST_DB="trading_system"
TEST_USER="trading_user"

echo "=========================================="
echo "PostgreSQL Failover Test"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to execute SQL on a pod
exec_sql() {
    local pod=$1
    local sql=$2
    kubectl exec -n $NAMESPACE $pod -- psql -U $TEST_USER -d $TEST_DB -c "$sql"
}

# Function to check replication status
check_replication() {
    echo -e "${YELLOW}Checking replication status...${NC}"
    kubectl exec -n $NAMESPACE $PRIMARY_POD -- psql -U $TEST_USER -d $TEST_DB -c "SELECT * FROM pg_stat_replication;"
}

# Function to check if pod is ready
wait_for_pod() {
    local pod=$1
    echo -e "${YELLOW}Waiting for pod $pod to be ready...${NC}"
    kubectl wait --for=condition=ready pod/$pod -n $NAMESPACE --timeout=300s
}

# Test 1: Create test data on primary
echo -e "\n${YELLOW}Test 1: Creating test data on primary...${NC}"
exec_sql $PRIMARY_POD "CREATE TABLE IF NOT EXISTS failover_test (id SERIAL PRIMARY KEY, test_time TIMESTAMP DEFAULT NOW(), test_data TEXT);"
exec_sql $PRIMARY_POD "INSERT INTO failover_test (test_data) VALUES ('Test before failover - $(date)');"

# Test 2: Verify data is replicated to replica
echo -e "\n${YELLOW}Test 2: Verifying data replication...${NC}"
sleep 5  # Wait for replication lag
REPLICA_COUNT=$(kubectl exec -n $NAMESPACE $REPLICA_POD -- psql -U $TEST_USER -d $TEST_DB -t -c "SELECT COUNT(*) FROM failover_test;" | tr -d ' ')
echo "Records on replica: $REPLICA_COUNT"

if [ "$REPLICA_COUNT" -gt "0" ]; then
    echo -e "${GREEN}✓ Replication is working${NC}"
else
    echo -e "${RED}✗ Replication failed${NC}"
    exit 1
fi

# Test 3: Check replication lag
echo -e "\n${YELLOW}Test 3: Checking replication lag...${NC}"
check_replication

# Test 4: Simulate primary failure
echo -e "\n${YELLOW}Test 4: Simulating primary failure...${NC}"
kubectl delete pod $PRIMARY_POD -n $NAMESPACE --grace-period=0 --force

# Test 5: Wait for primary to restart
echo -e "\n${YELLOW}Test 5: Waiting for primary to restart...${NC}"
wait_for_pod $PRIMARY_POD

# Test 6: Verify replica is still accessible
echo -e "\n${YELLOW}Test 6: Verifying replica accessibility during primary recovery...${NC}"
REPLICA_COUNT_AFTER=$(kubectl exec -n $NAMESPACE $REPLICA_POD -- psql -U $TEST_USER -d $TEST_DB -t -c "SELECT COUNT(*) FROM failover_test;" | tr -d ' ')
echo "Records on replica after primary failure: $REPLICA_COUNT_AFTER"

if [ "$REPLICA_COUNT_AFTER" == "$REPLICA_COUNT" ]; then
    echo -e "${GREEN}✓ Replica remained accessible during primary failure${NC}"
else
    echo -e "${RED}✗ Data inconsistency detected${NC}"
    exit 1
fi

# Test 7: Verify primary recovered and replication resumed
echo -e "\n${YELLOW}Test 7: Verifying primary recovery...${NC}"
sleep 10  # Wait for primary to fully recover
exec_sql $PRIMARY_POD "INSERT INTO failover_test (test_data) VALUES ('Test after recovery - $(date)');"
sleep 5  # Wait for replication
FINAL_COUNT=$(kubectl exec -n $NAMESPACE $REPLICA_POD -- psql -U $TEST_USER -d $TEST_DB -t -c "SELECT COUNT(*) FROM failover_test;" | tr -d ' ')

if [ "$FINAL_COUNT" -gt "$REPLICA_COUNT_AFTER" ]; then
    echo -e "${GREEN}✓ Primary recovered and replication resumed${NC}"
else
    echo -e "${RED}✗ Replication not working after recovery${NC}"
    exit 1
fi

# Cleanup
echo -e "\n${YELLOW}Cleaning up test data...${NC}"
exec_sql $PRIMARY_POD "DROP TABLE failover_test;"

echo -e "\n${GREEN}=========================================="
echo "All PostgreSQL Failover Tests Passed! ✓"
echo "==========================================${NC}"
