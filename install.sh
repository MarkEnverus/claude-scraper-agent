#!/bin/bash

# Claude Scraper Agent Installation Script
# Installs infrastructure code and registers Claude Code plugin

set -e  # Exit on error

echo "=================================="
echo "Claude Scraper Agent Installer"
echo "=================================="
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Parse command line arguments
SOURCING_PATH=""
SKIP_INFRA=false

print_usage() {
    echo "Usage: ./install.sh [OPTIONS] [SOURCING_PROJECT_PATH]"
    echo ""
    echo "Options:"
    echo "  --plugin-only    Install only the Claude Code plugin (skip infrastructure)"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Install both infrastructure and plugin:"
    echo "  ./install.sh /path/to/your-sourcing-project"
    echo ""
    echo "  # Install plugin only (useful if infrastructure is already installed):"
    echo "  ./install.sh --plugin-only"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --plugin-only)
            SKIP_INFRA=true
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            SOURCING_PATH="$1"
            shift
            ;;
    esac
done

# Validate sourcing path if not skipping infrastructure
if [ "$SKIP_INFRA" = false ]; then
    if [ -z "$SOURCING_PATH" ]; then
        echo "Error: Sourcing project path is required unless using --plugin-only"
        echo ""
        print_usage
        exit 1
    fi

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

    echo "📁 Sourcing Project: $SOURCING_PATH"
fi

echo "📁 Install Source: $SCRIPT_DIR"
echo ""

# Step 1: Install Infrastructure Code (if not skipped)
if [ "$SKIP_INFRA" = false ]; then
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
else
    echo "Step 1: Skipping infrastructure installation (--plugin-only)"
    echo ""
fi

# Step 2: Install Claude Code Plugin
echo "Step 2: Installing Claude Code Plugin..."
echo "---------------------------------------"

PLUGIN_DEST="$HOME/.claude/plugins/scraper-dev"
PLUGINS_JSON="$HOME/.claude/plugins/installed_plugins.json"

# Create plugin directory
mkdir -p "$PLUGIN_DEST"

# Copy plugin files
echo "  → Copying plugin files..."
cp -r "$SCRIPT_DIR/plugin/"* "$PLUGIN_DEST/"

# Register plugin in Claude Code
echo "  → Registering plugin with Claude Code..."

# Check if installed_plugins.json exists
if [ ! -f "$PLUGINS_JSON" ]; then
    echo "  → Creating installed_plugins.json..."
    mkdir -p "$(dirname "$PLUGINS_JSON")"
    cat > "$PLUGINS_JSON" << 'EOF'
{
  "version": 1,
  "plugins": {}
}
EOF
fi

# Use Python to safely update JSON
python3 << EOF
import json
import sys
from datetime import datetime, timezone

plugins_file = "$PLUGINS_JSON"
plugin_path = "$PLUGIN_DEST"

try:
    # Read existing plugins
    with open(plugins_file, 'r') as f:
        data = json.load(f)

    # Add or update scraper-dev entry
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    data['plugins']['scraper-dev'] = {
        'version': '1.0.0',
        'installedAt': timestamp,
        'lastUpdated': timestamp,
        'installPath': plugin_path,
        'isLocal': True
    }

    # Write back
    with open(plugins_file, 'w') as f:
        json.dump(data, f, indent=2)

    print("  ✅ Plugin registered successfully")

except Exception as e:
    print(f"  ❌ Error registering plugin: {e}", file=sys.stderr)
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  Plugin files copied but registration failed."
    echo "You may need to manually restart Claude Code."
    echo ""
fi

echo "✅ Plugin installed to: $PLUGIN_DEST"
echo ""

# Step 3: Verify Installation
echo "Step 3: Verifying Installation..."
echo "--------------------------------"

if [ "$SKIP_INFRA" = false ]; then
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

# Check plugin registration
if grep -q "scraper-dev" "$PLUGINS_JSON" 2>/dev/null; then
    echo "✅ Plugin registered in Claude Code"
else
    echo "❌ Plugin not registered (manual restart may be needed)"
fi

echo ""
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "Next Steps:"
echo "1. Restart Claude Code to load the plugin"
echo "   (Close and reopen your terminal with Claude Code)"
echo ""
echo "2. Verify plugin is available:"
echo "   Type '/create-scraper' in Claude Code"
echo ""
echo "3. Install Python dependencies:"
echo "   pip install redis boto3 click requests beautifulsoup4 playwright"
echo ""
echo "4. Configure environment variables:"
echo "   export REDIS_HOST=localhost"
echo "   export REDIS_PORT=6379"
echo "   export S3_BUCKET=your-bucket-name"
echo ""

if [ "$SKIP_INFRA" = false ]; then
    echo "5. Run tests (optional):"
    echo "   cd $SCRIPT_DIR"
    echo "   pytest tests/ -v"
    echo ""
fi

echo "Documentation:"
echo "- README: $SCRIPT_DIR/README.md"
echo "- Quick Reference: $SCRIPT_DIR/QUICK_REFERENCE.md"
echo ""
echo "Happy scraping! 🎉"
