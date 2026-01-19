#!/bin/bash
# Local OIDC Authentication Testing Script
#
# This script helps test the OIDC authentication implementation locally.
# It requires:
#   - OFFLINE_TOKEN environment variable set with your Red Hat SSO offline token
#   - jq installed for JSON parsing
#   - curl installed
#
# Usage:
#   export OFFLINE_TOKEN="your-offline-token"
#   ./scripts/test_oidc_local.sh
#
# Two authentication modes are supported:
#
# 1. Access Token Mode (default):
#    - Client fetches access token from SSO using offline token
#    - Client sends access token to MCP server
#    - Server validates JWT access token directly
#
# 2. Offline Token Mode (new):
#    - Client sends offline token directly to MCP server
#    - Server exchanges it for an access token automatically
#    - Server caches access token and refreshes as needed
#    - To enable: set OIDC_OFFLINE_TOKEN_ENABLED=true

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Konflux DevLake MCP Server - Local OIDC Testing ===${NC}"
echo ""

# Check prerequisites
if [ -z "$OFFLINE_TOKEN" ]; then
    echo -e "${RED}Error: OFFLINE_TOKEN environment variable is not set${NC}"
    echo "Please set it with: export OFFLINE_TOKEN='your-offline-token'"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is required but not installed${NC}"
    exit 1
fi

# Get access token from Red Hat SSO
echo -e "${YELLOW}Step 1: Getting access token from Red Hat SSO...${NC}"
TOKEN_RESPONSE=$(curl \
    --silent \
    --header "Accept: application/json" \
    --header "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "grant_type=refresh_token" \
    --data-urlencode "client_id=cloud-services" \
    --data-urlencode "refresh_token=${OFFLINE_TOKEN}" \
    "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token")

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq --raw-output ".access_token")

if [ "$ACCESS_TOKEN" == "null" ] || [ -z "$ACCESS_TOKEN" ]; then
    echo -e "${RED}Error: Failed to get access token${NC}"
    echo "Response: $TOKEN_RESPONSE"
    exit 1
fi

echo -e "${GREEN}Successfully obtained access token${NC}"

# Decode and display token claims (without verification)
echo ""
echo -e "${YELLOW}Step 2: Inspecting token claims...${NC}"
echo ""

# Extract payload from JWT (second part, base64 decoded)
PAYLOAD=$(echo "$ACCESS_TOKEN" | cut -d'.' -f2 | tr '_-' '/+' | base64 -d 2>/dev/null || echo "$ACCESS_TOKEN" | cut -d'.' -f2 | tr '_-' '/+' | base64 -D 2>/dev/null)

echo -e "${BLUE}Token Claims:${NC}"
echo "$PAYLOAD" | jq '.'

# Extract key values for OIDC configuration
ISSUER=$(echo "$PAYLOAD" | jq -r '.iss')
AUDIENCE=$(echo "$PAYLOAD" | jq -r '.aud')
AZP=$(echo "$PAYLOAD" | jq -r '.azp')
SUBJECT=$(echo "$PAYLOAD" | jq -r '.sub')
EXP=$(echo "$PAYLOAD" | jq -r '.exp')
EXP_DATE=$(date -r "$EXP" 2>/dev/null || date -d "@$EXP" 2>/dev/null || echo "unknown")

echo ""
echo -e "${BLUE}Key OIDC Configuration Values:${NC}"
echo -e "  Issuer (iss):       ${GREEN}${ISSUER}${NC}"
echo -e "  Audience (aud):     ${GREEN}${AUDIENCE}${NC}"
echo -e "  Authorized Party:   ${GREEN}${AZP}${NC}"
echo -e "  Subject (sub):      ${GREEN}${SUBJECT}${NC}"
echo -e "  Expires:            ${EXP_DATE}"

echo ""
echo -e "${YELLOW}Step 3: Suggested environment variables for MCP server:${NC}"
echo ""
echo -e "${BLUE}Option A - Access Token Mode (client exchanges token):${NC}"
echo "export OIDC_ENABLED=true"
echo "export OIDC_ISSUER_URL=\"${ISSUER}\""
echo "export OIDC_CLIENT_ID=\"${AZP}\""  # Use azp (authorized party) as client_id
echo "export OIDC_VERIFY_SSL=true"
echo ""
echo -e "${BLUE}Option B - Offline Token Mode (server exchanges token):${NC}"
echo "export OIDC_ENABLED=true"
echo "export OIDC_ISSUER_URL=\"${ISSUER}\""
echo "export OIDC_CLIENT_ID=\"${AZP}\""
echo "export OIDC_VERIFY_SSL=true"
echo "export OIDC_OFFLINE_TOKEN_ENABLED=true"
echo "export OIDC_TOKEN_EXCHANGE_CLIENT_ID=\"cloud-services\"  # Client ID for token exchange"
echo ""

# Check if server is running
MCP_SERVER_URL="${MCP_SERVER_URL:-http://localhost:3000}"

echo -e "${YELLOW}Step 4: Testing MCP server at ${MCP_SERVER_URL}...${NC}"

# Test health endpoint (should work without auth)
echo ""
echo -e "${BLUE}Testing /health endpoint (no auth required):${NC}"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "${MCP_SERVER_URL}/health" 2>/dev/null || echo -e "\n000")
HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | tail -1)
HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | sed '$d')

if [ "$HEALTH_STATUS" == "200" ]; then
    echo -e "${GREEN}Health check passed (HTTP $HEALTH_STATUS)${NC}"
    echo "$HEALTH_BODY" | jq '.' 2>/dev/null || echo "$HEALTH_BODY"
elif [ "$HEALTH_STATUS" == "000" ]; then
    echo -e "${RED}Server not reachable at ${MCP_SERVER_URL}${NC}"
    echo ""
    echo -e "${YELLOW}To start the server with OIDC enabled, run:${NC}"
    echo ""
    echo "# Start MySQL first"
    echo "docker compose up -d mysql"
    echo "sleep 10"
    echo ""
    echo "# Run server with OIDC"
    echo "export OIDC_ENABLED=true"
    echo "export OIDC_ISSUER_URL=\"${ISSUER}\""
    echo "export OIDC_CLIENT_ID=\"${AZP}\""
    echo ""
    echo "python3 konflux-devlake-mcp.py \\"
    echo "    --transport http \\"
    echo "    --host 0.0.0.0 \\"
    echo "    --port 3000 \\"
    echo "    --db-host localhost \\"
    echo "    --db-user root \\"
    echo "    --db-password test_password \\"
    echo "    --db-database lake \\"
    echo "    --log-level DEBUG"
    exit 0
else
    echo -e "${RED}Health check failed (HTTP $HEALTH_STATUS)${NC}"
    echo "$HEALTH_BODY"
fi

# Test MCP endpoint without auth (should get 401)
echo ""
echo -e "${BLUE}Testing /mcp endpoint WITHOUT auth (expecting 401):${NC}"
NOAUTH_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${MCP_SERVER_URL}/mcp" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' 2>/dev/null || echo -e "\n000")
NOAUTH_STATUS=$(echo "$NOAUTH_RESPONSE" | tail -1)
NOAUTH_BODY=$(echo "$NOAUTH_RESPONSE" | sed '$d')

if [ "$NOAUTH_STATUS" == "401" ]; then
    echo -e "${GREEN}Correctly rejected unauthenticated request (HTTP $NOAUTH_STATUS)${NC}"
    echo "$NOAUTH_BODY" | jq '.' 2>/dev/null || echo "$NOAUTH_BODY"
else
    echo -e "${YELLOW}Response (HTTP $NOAUTH_STATUS):${NC}"
    echo "$NOAUTH_BODY" | jq '.' 2>/dev/null || echo "$NOAUTH_BODY"
    if [ "$NOAUTH_STATUS" == "200" ]; then
        echo -e "${YELLOW}Note: Auth might be disabled or endpoint doesn't require auth${NC}"
    fi
fi

# Test MCP endpoint with auth (should work)
echo ""
echo -e "${BLUE}Testing /mcp endpoint WITH auth (expecting 200):${NC}"
AUTH_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${MCP_SERVER_URL}/mcp" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' 2>/dev/null || echo -e "\n000")
AUTH_STATUS=$(echo "$AUTH_RESPONSE" | tail -1)
AUTH_BODY=$(echo "$AUTH_RESPONSE" | sed '$d')

if [ "$AUTH_STATUS" == "200" ]; then
    echo -e "${GREEN}Authenticated request successful (HTTP $AUTH_STATUS)${NC}"
    echo "$AUTH_BODY" | jq '.' 2>/dev/null | head -50 || echo "$AUTH_BODY" | head -50
    echo "..."
elif [ "$AUTH_STATUS" == "401" ] || [ "$AUTH_STATUS" == "403" ]; then
    echo -e "${RED}Authentication failed (HTTP $AUTH_STATUS)${NC}"
    echo "$AUTH_BODY" | jq '.' 2>/dev/null || echo "$AUTH_BODY"
    echo ""
    echo -e "${YELLOW}Possible issues:${NC}"
    echo "  - OIDC_CLIENT_ID might not match the token's audience"
    echo "  - OIDC_ISSUER_URL might not match the token's issuer"
    echo "  - Token might have expired"
else
    echo -e "${YELLOW}Unexpected response (HTTP $AUTH_STATUS):${NC}"
    echo "$AUTH_BODY" | jq '.' 2>/dev/null || echo "$AUTH_BODY"
fi

# Test with offline token directly (if OIDC_OFFLINE_TOKEN_ENABLED is set on server)
echo ""
echo -e "${BLUE}Testing /mcp endpoint with OFFLINE token directly:${NC}"
echo "(This only works if server has OIDC_OFFLINE_TOKEN_ENABLED=true)"
OFFLINE_AUTH_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${MCP_SERVER_URL}/mcp" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -H "Authorization: Bearer ${OFFLINE_TOKEN}" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' 2>/dev/null || echo -e "\n000")
OFFLINE_AUTH_STATUS=$(echo "$OFFLINE_AUTH_RESPONSE" | tail -1)
OFFLINE_AUTH_BODY=$(echo "$OFFLINE_AUTH_RESPONSE" | sed '$d')

if [ "$OFFLINE_AUTH_STATUS" == "200" ]; then
    echo -e "${GREEN}Offline token authentication successful (HTTP $OFFLINE_AUTH_STATUS)${NC}"
    echo "$OFFLINE_AUTH_BODY" | jq '.' 2>/dev/null | head -20 || echo "$OFFLINE_AUTH_BODY" | head -20
    echo "..."
elif [ "$OFFLINE_AUTH_STATUS" == "401" ]; then
    echo -e "${YELLOW}Offline token not accepted (HTTP $OFFLINE_AUTH_STATUS)${NC}"
    echo "This is expected if OIDC_OFFLINE_TOKEN_ENABLED is not set to 'true'"
    echo "$OFFLINE_AUTH_BODY" | jq '.' 2>/dev/null || echo "$OFFLINE_AUTH_BODY"
else
    echo -e "${YELLOW}Response (HTTP $OFFLINE_AUTH_STATUS):${NC}"
    echo "$OFFLINE_AUTH_BODY" | jq '.' 2>/dev/null || echo "$OFFLINE_AUTH_BODY"
fi

echo ""
echo -e "${BLUE}=== Testing Complete ===${NC}"
