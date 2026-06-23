# Contributing to AI Engine

Thank you for considering contributing to AI Engine! This document provides guidelines for contributing.

## Getting Started

### Prerequisites
- Python 3.10+
- pip
- git

### Setup
```bash
# Clone the repository
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/
```

## Development Workflow

### 1. Create Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes
- Write code following style guidelines
- Add tests for new functionality
- Update documentation if needed

### 3. Run Tests
```bash
pytest tests/
```

### 4. Commit
```bash
git add .
git commit -m "feat: description of changes"
```

## Commit Message Format

Use conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Adding tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance

Examples:
```
feat: add new provider support
fix: resolve rate limiting issue
docs: update API documentation
test: add integration tests
```

## Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to public functions
- Keep functions focused and small

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=.

# Run specific test
pytest tests/test_ai_engine.py -v
```

## Pull Requests

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Questions?

Open an issue on GitHub or join our community.
