# Contributing to Claude Scraper Agent

Thank you for your interest in contributing!

## Installation from Repository

### For Users

If you want to use this tool:

```bash
# Clone the repository
git clone https://github.com/yourusername/claude_scraper_agent.git
cd claude_scraper_agent

# Run the installation script
./install.sh /path/to/your-sourcing-project

# Or install plugin only
./install.sh --plugin-only
```

The installation script will:
1. Copy infrastructure files to your project
2. Install the Claude Code plugin
3. Register it with Claude Code automatically

After installation:
- Restart Claude Code
- Type `/create-scraper` to start generating scrapers

### For Developers

If you want to contribute to development:

```bash
# Fork and clone your fork
git clone https://github.com/yourusername/claude_scraper_agent.git
cd claude_scraper_agent

# Install in development mode (plugin-only)
./install.sh --plugin-only

# Make changes to plugin files
vim plugin/agents/scraper-generator.md

# Changes are immediately reflected (no reinstall needed)
# Just restart Claude Code to see changes

# Run tests
pytest tests/ -v

# Before committing
pytest tests/ -v --cov=infrastructure
ruff check infrastructure/
```

## Development Workflow

### Making Changes to Agents

Agent prompts are in `plugin/agents/*.md`:

1. Edit the agent prompt file
2. Restart Claude Code
3. Test by invoking the agent: `/create-scraper`
4. Iterate

### Making Changes to Infrastructure

Infrastructure code is in `infrastructure/*.py`:

1. Edit the Python file
2. Add/update tests in `tests/`
3. Run tests: `pytest tests/ -v`
4. Update version in files if needed

### Testing Your Changes

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=infrastructure --cov-report=html

# Test installation script
./install.sh --plugin-only

# Test in Claude Code
/create-scraper
```

## Submitting Changes

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Add tests for new functionality
4. Ensure tests pass: `pytest tests/ -v`
5. Commit: `git commit -m "Description of changes"`
6. Push: `git push origin feature/your-feature`
7. Create a Pull Request

## Project Structure

```
claude_scraper_agent/
├── infrastructure/          # Python base classes
│   ├── hash_registry.py         # Redis hash deduplication
│   ├── logging_json.py          # Structured JSON logging
│   └── collection_framework.py  # BaseCollector class
├── plugin/                  # Claude Code plugin
│   ├── plugin.json              # Plugin manifest
│   ├── agents/                  # Agent prompts
│   │   ├── scraper-generator.md
│   │   ├── http-collector-generator.md
│   │   ├── website-parser-generator.md
│   │   ├── ftp-collector-generator.md
│   │   └── email-collector-generator.md
│   ├── commands/
│   │   └── create-scraper.md    # Slash command
│   └── skills/
│       └── scraper-creation.md  # Reusable skill
├── tests/                   # Unit tests
│   ├── test_hash_registry.py
│   ├── test_logging_json.py
│   └── test_collection_framework.py
├── examples/                # Example generated scrapers
├── docs/                    # Additional documentation
├── install.sh               # Installation script
├── uninstall.sh             # Uninstallation script
└── README.md                # Main documentation
```

## Coding Standards

### Python Code

- Follow PEP 8 style guide
- Use type hints where possible
- Write docstrings for all classes and methods
- Minimum 80% test coverage for new code

### Agent Prompts

- Clear, structured instructions
- Include examples
- Use markdown headings for organization
- Specify tools needed in frontmatter

### Commit Messages

Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

## Getting Help

- Issues: https://github.com/yourusername/claude_scraper_agent/issues
- Discussions: https://github.com/yourusername/claude_scraper_agent/discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
