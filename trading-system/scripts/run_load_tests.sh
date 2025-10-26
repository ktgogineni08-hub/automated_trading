#!/bin/bash
################################################################################
# Load Testing Runner Script
# Runs comprehensive load tests for the trading system
################################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_DIR="${PROJECT_ROOT}/tests/performance"
RESULTS_DIR="${TEST_DIR}/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${RESULTS_DIR}/load_test_${TIMESTAMP}.log"

# Default values
TARGET_HOST="${TARGET_HOST:-http://localhost:8000}"
SCENARIO="${SCENARIO:-baseline}"

# Create results directory
mkdir -p "${RESULTS_DIR}"

# Banner
echo -e "${BLUE}"
cat << 'BANNER'
═══════════════════════════════════════════════════════════════════════
  ___________  ___  ___  _____ _   _  _____   _______  _______ _______ 
 |_   _| ___ \/ _ \ |  \/  |_ _| \ | ||  _  | |_   _| \/ |_   _|  ___| 
   | | | |_/ / /_\ \| .  . || ||  \| || |  \/   | | | . . | | | |__   
   | | |    /|  _  || |\/| || || . ` || | __    | | | |\/| | | |  __|  
   | | | |\ \| | | || |  | || || |\  || |_\ \   | | | |  | | | | |___  
   \_/ \_| \_\_| |_/\_|  |_|___\_| \_/ \____/   \_/ \_|  |_/ \_\____/  
                                                                         
              LOAD TESTING SUITE
═══════════════════════════════════════════════════════════════════════
BANNER
echo -e "${NC}"

echo -e "${BLUE}Target: ${TARGET_HOST}${NC}"
echo -e "${BLUE}Scenario: ${SCENARIO}${NC}"
echo -e "${BLUE}Timestamp: ${TIMESTAMP}${NC}"
echo -e "${BLUE}Results: ${RESULTS_DIR}${NC}\n"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v locust &> /dev/null; then
    echo -e "${RED}❌ Locust not installed${NC}"
    echo "Install with: pip install locust"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met${NC}\n"

# Change to test directory
cd "${TEST_DIR}"

# Function to run a specific scenario
run_scenario() {
    local scenario=$1
    local users=$2
    local spawn_rate=$3
    local run_time=$4
    
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Running scenario: ${scenario}${NC}"
    echo -e "${BLUE}Users: ${users} | Spawn Rate: ${spawn_rate}/s | Duration: ${run_time}${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"
    
    local csv_prefix="${RESULTS_DIR}/${scenario}_${TIMESTAMP}"
    local html_report="${RESULTS_DIR}/${scenario}_${TIMESTAMP}.html"
    
    locust \
        -f locustfile.py \
        --headless \
        --users ${users} \
        --spawn-rate ${spawn_rate} \
        --run-time ${run_time} \
        --host ${TARGET_HOST} \
        --csv ${csv_prefix} \
        --html ${html_report} \
        --logfile ${LOG_FILE} \
        2>&1 | tee -a "${LOG_FILE}"
    
    if [ $? -eq 0 ]; then
        echo -e "\n${GREEN}✅ Scenario '${scenario}' completed successfully${NC}"
        echo -e "${GREEN}📊 Report: ${html_report}${NC}\n"
    else
        echo -e "\n${RED}❌ Scenario '${scenario}' failed${NC}\n"
        return 1
    fi
}

# Main execution
case "${SCENARIO}" in
    baseline)
        run_scenario "baseline" 10 2 "5m"
        ;;
    
    normal)
        run_scenario "normal_load" 50 5 "10m"
        ;;
    
    peak)
        run_scenario "peak_load" 200 10 "15m"
        ;;
    
    stress)
        run_scenario "stress_test" 500 20 "20m"
        ;;
    
    spike)
        run_scenario "spike_test" 300 50 "10m"
        ;;
    
    endurance)
        run_scenario "endurance_test" 100 5 "60m"
        ;;
    
    all)
        echo -e "${YELLOW}Running ALL load test scenarios...${NC}\n"
        run_scenario "baseline" 10 2 "5m"
        sleep 30
        run_scenario "normal_load" 50 5 "10m"
        sleep 30
        run_scenario "peak_load" 200 10 "15m"
        sleep 30
        run_scenario "stress_test" 500 20 "20m"
        ;;
    
    quick)
        echo -e "${YELLOW}Running quick test (2 minutes)...${NC}\n"
        run_scenario "quick_test" 10 5 "2m"
        ;;
    
    *)
        echo -e "${RED}Unknown scenario: ${SCENARIO}${NC}"
        echo "Available scenarios: baseline, normal, peak, stress, spike, endurance, all, quick"
        exit 1
        ;;
esac

# Print summary
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}LOAD TESTING COMPLETED${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Results directory: ${RESULTS_DIR}${NC}"
echo -e "${GREEN}Log file: ${LOG_FILE}${NC}"
echo ""
echo -e "${YELLOW}View results:${NC}"
echo -e "  ls -lh ${RESULTS_DIR}/*${TIMESTAMP}*"
echo -e "  open ${RESULTS_DIR}/*${TIMESTAMP}.html"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

exit 0
