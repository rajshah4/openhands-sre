#!/bin/bash
# Fix a demo service - simulates what self-hosted OpenHands would do
# Usage: ./scripts/fix_demo.sh [service1|service2|service3]

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SERVICE=${1:-service1}
CONTAINER="openhands-gepa-demo"

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  Executing remediation (self-hosted OpenHands would do this)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

case $SERVICE in
    service1|lockfile)
        echo -e "${YELLOW}Scenario:${NC} Stale lockfile"
        echo -e "${YELLOW}Risk Level:${NC} MEDIUM"
        echo -e "${YELLOW}Action:${NC} Removing stale lockfile"
        echo ""
        echo -e "$ docker exec $CONTAINER rm -f /tmp/service.lock"
        docker exec $CONTAINER rm -f /tmp/service.lock
        ;;
    service2|ready)
        echo -e "${YELLOW}Scenario:${NC} Readiness probe failure"
        echo -e "${YELLOW}Risk Level:${NC} LOW"
        echo -e "${YELLOW}Action:${NC} Creating readiness flag"
        echo ""
        echo -e "$ docker exec $CONTAINER touch /tmp/ready.flag"
        docker exec $CONTAINER touch /tmp/ready.flag
        ;;
    service3|config)
        echo -e "${YELLOW}Scenario:${NC} Bad environment config"
        echo -e "${YELLOW}Risk Level:${NC} MEDIUM"
        echo -e "${YELLOW}Action:${NC} This requires restarting with correct env vars"
        echo ""
        echo "Run: docker rm -f $CONTAINER && docker run -d -p 15000:5000 -e REQUIRED_API_KEY=secret --name $CONTAINER openhands-gepa-sre-target:latest"
        exit 0
        ;;
    *)
        echo "Unknown service: $SERVICE"
        echo "Usage: ./scripts/fix_demo.sh [service1|service2|service3]"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✓ Remediation complete${NC}"
echo ""
echo -e "Verify: curl http://localhost:15000/$SERVICE"
echo ""
