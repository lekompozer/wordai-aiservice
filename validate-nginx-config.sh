#!/bin/bash

# ============================================================================
# Validate NGINX Configuration Syntax Only (No Docker Required)
# ============================================================================

set -e

echo "=========================================="
echo "NGINX Configuration Validation"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if nginx is installed
if command -v nginx &> /dev/null; then
    echo -e "${GREEN}✓ nginx command found${NC}"

    # Test with nginx directly
    echo -e "${YELLOW}Testing NGINX configuration syntax...${NC}"
    nginx -t -c nginx/nginx.conf -p "$(pwd)/"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ NGINX configuration is valid!${NC}"
    else
        echo -e "${RED}✗ NGINX configuration has syntax errors${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}nginx command not found on this system${NC}"
    echo "Performing basic validation checks..."

    # Check files exist
    echo ""
    echo "Checking required files:"
    if [ -f "nginx/nginx.conf" ]; then
        echo -e "${GREEN}✓ nginx/nginx.conf exists${NC}"
    else
        echo -e "${RED}✗ nginx/nginx.conf not found${NC}"
        exit 1
    fi

    if [ -f "nginx/conf.d/ai-wordai.conf" ]; then
        echo -e "${GREEN}✓ nginx/conf.d/ai-wordai.conf exists${NC}"
    else
        echo -e "${RED}✗ nginx/conf.d/ai-wordai.conf not found${NC}"
        exit 1
    fi

    # Check for common syntax errors
    echo ""
    echo "Checking for common syntax errors:"

    # Check for unmatched braces
    OPEN_BRACES=$(grep -o '{' nginx/nginx.conf nginx/conf.d/*.conf | wc -l | tr -d ' ')
    CLOSE_BRACES=$(grep -o '}' nginx/nginx.conf nginx/conf.d/*.conf | wc -l | tr -d ' ')

    if [ "$OPEN_BRACES" -eq "$CLOSE_BRACES" ]; then
        echo -e "${GREEN}✓ Braces balanced ($OPEN_BRACES opening, $CLOSE_BRACES closing)${NC}"
    else
        echo -e "${RED}✗ Unmatched braces (opening: $OPEN_BRACES, closing: $CLOSE_BRACES)${NC}"
        exit 1
    fi

    # Check for missing semicolons (basic check)
    if grep -n '^[[:space:]]*[a-z_].*[^{;]$' nginx/nginx.conf nginx/conf.d/*.conf | grep -v '#' > /tmp/nginx_check.txt 2>/dev/null; then
        echo -e "${YELLOW}⚠ Possible missing semicolons found:${NC}"
        head -5 /tmp/nginx_check.txt
        echo "(This may be a false positive)"
    else
        echo -e "${GREEN}✓ No obvious missing semicolons${NC}"
    fi

    # Check upstream definitions
    echo ""
    echo "Checking upstream definitions:"
    if grep -q "upstream python_backend" nginx/conf.d/ai-wordai.conf; then
        echo -e "${GREEN}✓ python_backend upstream defined${NC}"
    else
        echo -e "${RED}✗ python_backend upstream not found${NC}"
    fi

    if grep -q "upstream nodejs_payment" nginx/conf.d/ai-wordai.conf; then
        echo -e "${GREEN}✓ nodejs_payment upstream defined${NC}"
    else
        echo -e "${RED}✗ nodejs_payment upstream not found${NC}"
    fi

    # Check SSL certificate paths
    echo ""
    echo "Checking SSL configuration:"
    if grep -q "ssl_certificate.*ai.wordai.pro" nginx/conf.d/ai-wordai.conf; then
        echo -e "${GREEN}✓ SSL certificate path configured${NC}"
    else
        echo -e "${YELLOW}⚠ SSL certificate path not found${NC}"
    fi

    # Check rate limiting
    echo ""
    echo "Checking rate limiting:"
    if grep -q "limit_req_zone" nginx/conf.d/ai-wordai.conf; then
        echo -e "${GREEN}✓ Rate limiting configured${NC}"
        grep "limit_req_zone" nginx/conf.d/ai-wordai.conf
    else
        echo -e "${YELLOW}⚠ Rate limiting not configured${NC}"
    fi

    # Check important locations
    echo ""
    echo "Checking location blocks:"
    LOCATIONS=$(grep "location " nginx/conf.d/ai-wordai.conf | wc -l | tr -d ' ')
    echo -e "${GREEN}✓ Found $LOCATIONS location blocks${NC}"

    if grep -q "location /api/v1/payments" nginx/conf.d/ai-wordai.conf; then
        echo -e "${GREEN}✓ Payment API route configured${NC}"
    else
        echo -e "${RED}✗ Payment API route not found${NC}"
    fi

    if grep -q "location /sepay" nginx/conf.d/ai-wordai.conf; then
        echo -e "${GREEN}✓ SePay webhook route configured${NC}"
    else
        echo -e "${RED}✗ SePay webhook route not found${NC}"
    fi

    echo ""
    echo -e "${GREEN}Basic validation passed!${NC}"
    echo -e "${YELLOW}Note: Full syntax validation requires nginx or Docker${NC}"
    echo ""
    echo "To validate on production server:"
    echo "  ssh root@104.248.147.155 'docker run --rm -v \$(pwd)/nginx:/etc/nginx:ro nginx:1.26-alpine nginx -t'"
fi

echo ""
echo "=========================================="
echo "Configuration Summary"
echo "=========================================="
echo ""
echo "Files validated:"
echo "  - nginx/nginx.conf ($(wc -l < nginx/nginx.conf) lines)"
echo "  - nginx/conf.d/ai-wordai.conf ($(wc -l < nginx/conf.d/ai-wordai.conf) lines)"
echo ""
echo "Next steps:"
echo "  1. Commit changes: git add . && git commit -m 'feat: Add NGINX configuration'"
echo "  2. Push to GitHub: git push origin main"
echo "  3. Deploy to production: See PHASE1_NGINX_DEPLOYMENT.md"
echo ""
