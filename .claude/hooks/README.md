# Claude Code Hooks

## PostToolUse Hook

**Purpose**: Automatically run code quality checks (ruff and mypy) after editing Python files.

**Triggers**: After `Write`, `Edit`, or `NotebookEdit` tool usage on `.py` files

**Behavior**:
- ✅ Runs `ruff check` (linter + import sorting)
- ✅ Runs `mypy` (static type checking)
- ⚠️  Non-blocking (always returns exit code 0)
- 🔇 Only outputs if issues found

**Requirements**:
- `ruff` (install: `uv pip install ruff`)
- `mypy` (install: `uv pip install mypy`)
- `jq` (install: `brew install jq`)

**Configuration**:
Edit `.claude/hooks/PostToolUse.sh` to customize:
- Change ruff rules: `--select=E,F,W,I`
- Change mypy strictness: `--ignore-missing-imports`
- Make blocking: Change `exit 0` to `exit 1` on errors

**Testing**:
```bash
# Manually test the hook
echo '{"tool":"Write","parameters":{"file_path":"test.py"}}' | .claude/hooks/PostToolUse.sh
```

**Disable**:
```bash
# Temporarily disable
chmod -x .claude/hooks/PostToolUse.sh

# Re-enable
chmod +x .claude/hooks/PostToolUse.sh
```

---

**Created**: January 14, 2026
**Last Updated**: January 14, 2026
