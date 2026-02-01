# Contributing to ricet

Thank you for your interest in contributing to ricet!

## Development Setup

```bash
git clone https://github.com/lucafusarbassini/research-automation.git
cd research-automation
pip install -e ".[dev]"
```

## Running Tests

```bash
python3 -m pytest tests/ -v
```

## Code Style

This project uses [black](https://github.com/psf/black) for formatting and [isort](https://pycqa.github.io/isort/) for import sorting. Run them before committing:

```bash
black .
isort .
```

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests and formatting
5. Submit a pull request

## Reporting Issues

Open an issue on [GitHub Issues](https://github.com/lucafusarbassini/research-automation/issues).
