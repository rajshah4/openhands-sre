#!/bin/bash
# Preflight checks for the OpenHands SRE + Jenkins demo.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-15000}"
SERVICE1_EXPECTED_HTTP="${SERVICE1_EXPECTED_HTTP:-200}"
MCP_HOST="${MCP_HOST:-127.0.0.1}"
MCP_PORT="${MCP_PORT:-8080}"
PUBLIC_MCP_URL="${PUBLIC_MCP_URL:-}"
JENKINS_URL="${JENKINS_URL:-http://127.0.0.1:8081}"
JENKINS_USER="${JENKINS_USER:-admin}"
JENKINS_PASSWORD="${JENKINS_PASSWORD:-admin}"
JENKINS_JOB="${JENKINS_JOB:-openhands-sre-demo}"
REPO="${GITHUB_REPO:-rajshah4/openhands-sre}"
WEBHOOK_SECRET_FILE="${WEBHOOK_SECRET_FILE:-${ROOT_DIR}/.demo_webhook_secret}"
WEBHOOK_REQUIRED="${WEBHOOK_REQUIRED:-0}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo -e "${RED}FAIL${NC} missing command: $1"
        exit 1
    fi
}

infer_public_mcp_url() {
    if [[ -n "$PUBLIC_MCP_URL" ]]; then
        return 0
    fi
    if ! command -v tailscale >/dev/null 2>&1; then
        return 1
    fi

    local funnel_status base_url
    funnel_status="$(tailscale funnel status 2>/dev/null || true)"
    base_url="$(
        printf '%s\n' "$funnel_status" \
            | grep -E '^https://' \
            | awk '{print $1}' \
            | grep -v ':8443$' \
            | head -1
    )"

    if [[ -z "$base_url" ]]; then
        base_url="$(
            printf '%s\n' "$funnel_status" \
                | grep -E '^https://' \
                | awk '{print $1}' \
                | head -1
        )"
    fi

    if [[ -n "$base_url" ]]; then
        PUBLIC_MCP_URL="${base_url%/}/mcp"
        export PUBLIC_MCP_URL
        return 0
    fi
    return 1
}

check_http() {
    local label="$1"
    local url="$2"
    local expected="${3:-200}"
    local code

    code="$(curl -sS -o /dev/null -w "%{http_code}" "$url" || true)"
    if [[ "$code" == "$expected" ]]; then
        echo -e "${GREEN}PASS${NC} ${label}: HTTP ${code} (${url})"
    else
        echo -e "${RED}FAIL${NC} ${label}: expected HTTP ${expected}, got ${code} (${url})"
        return 1
    fi
}

check_jenkins_job() {
    local payload
    payload="$(
        curl -sS -u "${JENKINS_USER}:${JENKINS_PASSWORD}" \
            "${JENKINS_URL}/job/${JENKINS_JOB}/api/json" || true
    )"

    if printf '%s' "$payload" | grep -q "\"name\":\"${JENKINS_JOB}\""; then
        echo -e "${GREEN}PASS${NC} Jenkins job '${JENKINS_JOB}' is present"
    else
        echo -e "${RED}FAIL${NC} Jenkins job '${JENKINS_JOB}' not found at ${JENKINS_URL}"
        return 1
    fi
}

check_github_auth() {
    if gh auth status >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC} GitHub CLI authenticated"
    else
        echo -e "${RED}FAIL${NC} GitHub CLI is not authenticated"
        return 1
    fi
}

check_repo_access() {
    if gh repo view "$REPO" >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC} GitHub repo accessible: ${REPO}"
    else
        echo -e "${RED}FAIL${NC} Cannot access GitHub repo: ${REPO}"
        return 1
    fi
}

check_github_webhook() {
    local webhook_url payload
    webhook_url="$(python3 - <<'PY'
from urllib.parse import urlparse
import os
public_mcp_url = os.environ.get("PUBLIC_MCP_URL", "https://macbook-pro.tail21d104.ts.net/mcp")
parsed = urlparse(public_mcp_url)
path = parsed.path.rstrip("/")
print(f"{parsed.scheme}://{parsed.netloc}{path}/github-webhook")
PY
)"
    payload="$(gh api "repos/${REPO}/hooks" || true)"
    if printf '%s' "$payload" | grep -q "\"url\":\"${webhook_url}\""; then
        echo -e "${GREEN}PASS${NC} GitHub webhook present: ${webhook_url}"
    else
        echo -e "${RED}FAIL${NC} GitHub webhook missing: ${webhook_url}"
        return 1
    fi
}

main() {
    cd "$ROOT_DIR"

    require_cmd curl
    require_cmd docker
    require_cmd gh
    infer_public_mcp_url || true

    local failed=0

    echo "=========================================="
    echo "  OpenHands Demo Preflight"
    echo "=========================================="

    if docker info >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC} Docker daemon reachable"
    else
        echo -e "${RED}FAIL${NC} Docker daemon not reachable"
        failed=1
    fi

    if docker ps --format '{{.Names}}' | grep -qx 'openhands-gepa-demo'; then
        echo -e "${GREEN}PASS${NC} Demo container is running"
    else
        echo -e "${YELLOW}WARN${NC} Demo container is not running"
        failed=1
    fi

    check_http "Host app index" "http://${APP_HOST}:${APP_PORT}/" "200" || failed=1
    check_http "Host service1" "http://${APP_HOST}:${APP_PORT}/service1" "${SERVICE1_EXPECTED_HTTP}" || failed=1
    check_http "Local MCP" "http://${MCP_HOST}:${MCP_PORT}/" "200" || failed=1
    if [[ -n "$PUBLIC_MCP_URL" ]]; then
        check_http "Public MCP" "${PUBLIC_MCP_URL}" "200" || failed=1
    else
        echo -e "${RED}FAIL${NC} Public MCP URL not set and could not be inferred from Tailscale Funnel"
        failed=1
    fi
    check_http "Jenkins login" "${JENKINS_URL}/login" "200" || failed=1
    check_jenkins_job || failed=1
    check_github_auth || failed=1
    check_repo_access || failed=1
    if [[ "$WEBHOOK_REQUIRED" -eq 1 ]] || [[ -f "$WEBHOOK_SECRET_FILE" ]]; then
        check_github_webhook || failed=1
    fi

    echo
    if [[ "$failed" -eq 0 ]]; then
        echo -e "${GREEN}Preflight passed.${NC} Safe to run the live demo."
    else
        echo -e "${RED}Preflight failed.${NC} Fix the failing checks before the live demo."
        exit 1
    fi
}

main "$@"
