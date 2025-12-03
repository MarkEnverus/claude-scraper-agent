#!/bin/bash

# Claude Scraper Agent - Infrastructure Installer
# Downloads and installs infrastructure files from GitHub

set -e  # Exit on error

GITHUB_REPO="yourusername/claude_scraper_agent"
GITHUB_BRANCH="main"
BASE_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"

echo "========================================"
echo "Scraper Agent Infrastructure Installer"
echo "========================================"
echo ""

# Check if sourcing path is provided
if [ -z "$1" ]; then
    echo "Usage: ./install-infrastructure.sh /path/to/your-sourcing-project"
    echo ""
    echo "Example:"
    echo "  ./install-infrastructure.sh /Users/username/projects/my-sourcing-project"
    echo ""
    echo "This will install:"
    echo "  - hash_registry.py → sourcing/scraping/commons/"
    echo "  - logging_json.py → sourcing/common/"
    echo "  - collection_framework.py → sourcing/scraping/commons/"
    echo "  - kafka_utils.py → sourcing/scraping/commons/"
    exit 1
fi

SOURCING_PATH="$1"

# Validate sourcing project path
if [ ! -d "$SOURCING_PATH" ]; then
    echo "Error: Directory not found: $SOURCING_PATH"
    exit 1
fi

if [ ! -d "$SOURCING_PATH/sourcing" ]; then
    echo "Warning: Not a standard sourcing project (missing sourcing/ directory)"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📁 Target Project: $SOURCING_PATH"
echo "📦 Source: GitHub ($GITHUB_REPO)"
echo ""

# Create directories
echo "Creating directories..."
mkdir -p "$SOURCING_PATH/sourcing/scraping/commons"
mkdir -p "$SOURCING_PATH/sourcing/common"

# Download files
echo ""
echo "Downloading infrastructure files..."
echo "-----------------------------------"

echo "  → hash_registry.py..."
curl -fsSL "$BASE_URL/infrastructure/hash_registry.py" \
    -o "$SOURCING_PATH/sourcing/scraping/commons/hash_registry.py"

echo "  → logging_json.py..."
curl -fsSL "$BASE_URL/infrastructure/logging_json.py" \
    -o "$SOURCING_PATH/sourcing/common/logging_json.py"

echo "  → collection_framework.py..."
curl -fsSL "$BASE_URL/infrastructure/collection_framework.py" \
    -o "$SOURCING_PATH/sourcing/scraping/commons/collection_framework.py"

echo "  → kafka_utils.py..."
curl -fsSL "$BASE_URL/infrastructure/kafka_utils.py" \
    -o "$SOURCING_PATH/sourcing/scraping/commons/kafka_utils.py"

echo ""
echo "Verifying installation..."
echo "------------------------"

# Verify files
if [ -f "$SOURCING_PATH/sourcing/scraping/commons/hash_registry.py" ]; then
    echo "✅ hash_registry.py"
else
    echo "❌ hash_registry.py missing"
fi

if [ -f "$SOURCING_PATH/sourcing/common/logging_json.py" ]; then
    echo "✅ logging_json.py"
else
    echo "❌ logging_json.py missing"
fi

if [ -f "$SOURCING_PATH/sourcing/scraping/commons/collection_framework.py" ]; then
    echo "✅ collection_framework.py"
else
    echo "❌ collection_framework.py missing"
fi

if [ -f "$SOURCING_PATH/sourcing/scraping/commons/kafka_utils.py" ]; then
    echo "✅ kafka_utils.py"
else
    echo "❌ kafka_utils.py missing"
fi

echo ""
echo "========================================"
echo "Infrastructure Installation Complete!"
echo "========================================"
echo ""
echo "Next Steps:"
echo ""
echo "1. Install Python dependencies:"
echo "   uv pip install redis boto3 click requests beautifulsoup4 playwright confluent-kafka pydantic"
echo ""
echo "2. Configure environment variables:"
echo "   export REDIS_HOST=localhost"
echo "   export REDIS_PORT=6379"
echo "   export S3_BUCKET=your-bucket-name"
echo ""
echo "3. If you haven't already, install the Claude Code plugin:"
echo "   claude plugin marketplace add https://github.com/$GITHUB_REPO"
echo "   claude plugin install scraper-dev@scraper-agent-marketplace"
echo ""
echo "4. Restart Claude Code and type '/create-scraper' to start!"
echo ""
