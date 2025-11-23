#!/bin/bash

# Claude Scraper Agent Installation Script
# Installs infrastructure code and Claude Code plugin

set -e  # Exit on error

echo "=================================="
echo "Claude Scraper Agent Installer"
echo "=================================="
echo ""

# Check if sourcing project path is provided
if [ -z "$1" ]; then
    echo "Usage: ./install.sh /path/to/pr.prt.sourcing"
    echo ""
    echo "Example:"
    echo "  ./install.sh /Users/mark.johnson/Desktop/source/repos/enverus-pr/pr.prt.sourcing"
    exit 1
fi

SOURCING_PATH="$1"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Validate sourcing project path
if [ ! -d "$SOURCING_PATH" ]; then
    echo "Error: Directory not found: $SOURCING_PATH"
    exit 1
fi

if [ ! -d "$SOURCING_PATH/sourcing" ]; then
    echo "Error: Not a valid sourcing project (missing sourcing/ directory)"
    exit 1
fi

echo "📁 Sourcing Project: $SOURCING_PATH"
echo "📁 Install Source: $SCRIPT_DIR"
echo ""

# Step 1: Install Infrastructure Code
echo "Step 1: Installing Infrastructure Code..."
echo "----------------------------------------"

# Create directories if they don't exist
mkdir -p "$SOURCING_PATH/sourcing/scraping/commons"
mkdir -p "$SOURCING_PATH/sourcing/common"

# Copy infrastructure files
echo "  → Copying hash_registry.py..."
cp "$SCRIPT_DIR/infrastructure/hash_registry.py" "$SOURCING_PATH/sourcing/scraping/commons/"

echo "  → Copying logging_json.py..."
cp "$SCRIPT_DIR/infrastructure/logging_json.py" "$SOURCING_PATH/sourcing/common/"

echo "  → Copying collection_framework.py..."
cp "$SCRIPT_DIR/infrastructure/collection_framework.py" "$SOURCING_PATH/sourcing/scraping/commons/"

echo "✅ Infrastructure code installed"
echo ""

# Step 2: Install Claude Code Plugin
echo "Step 2: Installing Claude Code Plugin..."
echo "---------------------------------------"

PLUGIN_DEST="$HOME/.claude/plugins/scraper-dev"

# Create plugin directory
mkdir -p "$PLUGIN_DEST"

# Copy plugin files
echo "  → Copying plugin files..."
cp -r "$SCRIPT_DIR/plugin/"* "$PLUGIN_DEST/"

echo "✅ Plugin installed to: $PLUGIN_DEST"
echo ""

# Step 3: Verify Installation
echo "Step 3: Verifying Installation..."
echo "--------------------------------"

# Check infrastructure files
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

# Check plugin files
if [ -f "$PLUGIN_DEST/plugin.json" ]; then
    echo "✅ Plugin manifest"
else
    echo "❌ Plugin manifest missing"
fi

if [ -d "$PLUGIN_DEST/agents" ]; then
    echo "✅ Agent prompts"
else
    echo "❌ Agent prompts missing"
fi

echo ""
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "Next Steps:"
echo "1. Restart Claude Code (or reload plugins)"
echo "2. Verify plugin: Type '/create-scraper' in Claude Code"
echo "3. Install Python dependencies:"
echo "   pip install redis boto3 click requests beautifulsoup4"
echo ""
echo "4. Configure environment:"
echo "   export REDIS_HOST=localhost"
echo "   export REDIS_PORT=6379"
echo "   export S3_BUCKET=your-bucket-name"
echo ""
echo "5. Run tests (optional):"
echo "   cd $SCRIPT_DIR"
echo "   pytest tests/ -v"
echo ""
echo "Documentation:"
echo "- README: $SCRIPT_DIR/README.md"
echo "- Plan: $SOURCING_PATH/SCRAPER_AGENT_PLAN.md"
echo ""
echo "Happy scraping! 🎉"
