#!/bin/bash
# OpenHands SRE Demo Setup Script
# This script sets up the local environment for the demo

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  OpenHands SRE Demo Setup"
echo "=========================================="
echo ""

# Check Docker
echo -n "Checking Docker... "
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo -e "${GREEN}✓ Docker is running${NC}"
else
    echo -e "${RED}✗ Docker is not running${NC}"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

# Build the target service image
echo ""
echo "Building target service Docker image..."
docker build -t openhands-gepa-sre-target:latest target_service/
echo -e "${GREEN}✓ Image built${NC}"

# Stop existing container if running
echo ""
echo -n "Stopping existing container... "
docker rm -f openhands-gepa-demo 2>/dev/null || true
echo -e "${GREEN}✓ Done${NC}"

# Start the container
echo ""
echo "Starting demo container..."
docker run -d -p 15000:5000 --name openhands-gepa-demo openhands-gepa-sre-target:latest
echo -e "${GREEN}✓ Container started on port 15000${NC}"

# Wait for service to be ready
echo ""
echo -n "Waiting for service... "
sleep 2
if curl -s http://localhost:15000/ > /dev/null; then
    echo -e "${GREEN}✓ Service is responding${NC}"
else
    echo -e "${RED}✗ Service not responding${NC}"
    exit 1
fi

# Check Tailscale (optional)
echo ""
echo -n "Checking Tailscale... "
if command -v tailscale &> /dev/null; then
    if tailscale status &> /dev/null; then
        echo -e "${GREEN}✓ Tailscale is connected${NC}"
        
        echo ""
        echo -n "Checking Tailscale Funnel... "
        if tailscale funnel status 2>&1 | grep -q "proxy"; then
            FUNNEL_URL=$(tailscale funnel status 2>&1 | grep "https://" | head -1 | awk '{print $1}')
            echo -e "${GREEN}✓ Funnel is running${NC}"
            echo -e "   Public URL: ${GREEN}${FUNNEL_URL}${NC}"
        else
            echo -e "${YELLOW}○ Funnel not running${NC}"
            echo ""
            echo "To expose the service publicly, run:"
            echo "  tailscale funnel 15000"
        fi
    else
        echo -e "${YELLOW}○ Tailscale not connected${NC}"
        echo "  Run 'tailscale up' to connect"
    fi
else
    echo -e "${YELLOW}○ Tailscale not installed${NC}"
    echo "  Install from: https://tailscale.com/download"
    echo "  (Optional - only needed for OpenHands Cloud integration)"
fi

# Summary
echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Local URLs:"
echo "  Index:    http://localhost:15000/"
echo "  Service1: http://localhost:15000/service1 (stale lockfile)"
echo "  Service2: http://localhost:15000/service2 (readiness probe)"
echo "  Service3: http://localhost:15000/service3 (env config)"
echo ""
echo "Quick commands:"
echo "  Break service1: docker exec openhands-gepa-demo touch /tmp/service.lock"
echo "  Fix service1:   docker exec openhands-gepa-demo rm -f /tmp/service.lock"
echo "  Fix service2:   docker exec openhands-gepa-demo touch /tmp/ready.flag"
echo ""
echo "To create a demo issue:"
echo "  uv run python scripts/create_demo_issue.py --scenario stale_lockfile"
echo ""
