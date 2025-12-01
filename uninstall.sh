#!/bin/bash

# Claude Scraper Agent Uninstallation Script
# Removes the Claude Code plugin

set -e  # Exit on error

echo "===================================="
echo "Claude Scraper Agent Uninstaller"
echo "===================================="
echo ""

PLUGIN_DEST="$HOME/.claude/plugins/scraper-dev"
PLUGINS_JSON="$HOME/.claude/plugins/installed_plugins.json"

# Check if plugin exists
if [ ! -d "$PLUGIN_DEST" ]; then
    echo "Plugin not found at: $PLUGIN_DEST"
    echo "Nothing to uninstall."
    exit 0
fi

echo "This will remove the scraper-dev plugin from Claude Code."
echo "Plugin location: $PLUGIN_DEST"
echo ""
read -p "Continue with uninstallation? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

echo ""
echo "Step 1: Removing plugin files..."
echo "--------------------------------"

rm -rf "$PLUGIN_DEST"

if [ ! -d "$PLUGIN_DEST" ]; then
    echo "✅ Plugin files removed"
else
    echo "❌ Failed to remove plugin files"
    exit 1
fi

echo ""
echo "Step 2: Unregistering plugin..."
echo "--------------------------------"

if [ -f "$PLUGINS_JSON" ]; then
    # Use Python to safely update JSON
    python3 << EOF
import json
import sys

plugins_file = "$PLUGINS_JSON"

try:
    # Read existing plugins
    with open(plugins_file, 'r') as f:
        data = json.load(f)

    # Remove scraper-dev entry if it exists
    if 'scraper-dev' in data.get('plugins', {}):
        del data['plugins']['scraper-dev']

        # Write back
        with open(plugins_file, 'w') as f:
            json.dump(data, f, indent=2)

        print("✅ Plugin unregistered from Claude Code")
    else:
        print("⚠️  Plugin was not registered")

except Exception as e:
    print(f"❌ Error unregistering plugin: {e}", file=sys.stderr)
    sys.exit(1)
EOF
else
    echo "⚠️  installed_plugins.json not found"
fi

echo ""
echo "===================================="
echo "Uninstallation Complete!"
echo "===================================="
echo ""
echo "Note: This script only removes the Claude Code plugin."
echo "Infrastructure files in your sourcing project were not touched."
echo ""
echo "To remove infrastructure files manually:"
echo "  rm sourcing/scraping/commons/hash_registry.py"
echo "  rm sourcing/scraping/commons/collection_framework.py"
echo "  rm sourcing/common/logging_json.py"
echo ""
echo "Restart Claude Code to complete the uninstallation."
echo ""
