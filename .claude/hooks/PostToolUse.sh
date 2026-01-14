#!/bin/bash
# PostToolUse hook: Run ruff and mypy on Python file changes
# Triggered after Write, Edit, or NotebookEdit tool usage

# Parse hook input (Claude Code provides JSON on stdin)
TOOL_NAME=$(jq -r '.tool' 2>/dev/null)
FILE_PATH=$(jq -r '.parameters.file_path // .parameters.notebook_path // empty' 2>/dev/null)

# Only run on Python files
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    exit 0
fi

# Only run for Write, Edit, NotebookEdit
if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" && "$TOOL_NAME" != "NotebookEdit" ]]; then
    exit 0
fi

# Check if file exists
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

echo "🔍 Running code quality checks on $FILE_PATH..."

# Run ruff (linter + formatter check)
if command -v ruff &> /dev/null; then
    echo "Running ruff..."
    if ! uv run ruff check "$FILE_PATH" --select=E,F,W,I --quiet 2>&1; then
        echo "⚠️  Ruff found issues (non-blocking)"
    else
        echo "✅ Ruff: No issues"
    fi
else
    echo "ℹ️  Ruff not installed, skipping"
fi

# Run mypy (type checking)
if command -v mypy &> /dev/null; then
    echo "Running mypy..."
    if ! uv run mypy "$FILE_PATH" --ignore-missing-imports --no-error-summary 2>&1 | grep -v "Success:"; then
        echo "⚠️  Mypy found type issues (non-blocking)"
    else
        echo "✅ Mypy: No type errors"
    fi
else
    echo "ℹ️  Mypy not installed, skipping"
fi

# Always exit 0 (non-blocking)
exit 0
