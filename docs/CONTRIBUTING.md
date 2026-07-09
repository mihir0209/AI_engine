# Contributing Guide

## Welcome!

Thank you for considering contributing to AI Engine! This document provides guidelines for contributing.

---

## Development Setup

### Prerequisites

- Python 3.10+
- pip
- git

### Setup

```bash
# Fork and clone
git clone <your-fork-url>
cd AI_engine

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev,all]"

# Install dev dependencies
pip install pytest pytest-cov ruff mypy

# Create .env file
cp .env.example .env
```

---

## Development Workflow

### 1. Create Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `refactor/` - Code refactoring
- `test/` - Adding tests

### 2. Make Changes

- Write code following style guidelines
- Add tests for new functionality
- Update documentation if needed

### 3. Run Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=.

# Run specific test file
pytest tests/test_ai_engine.py -v
```

### 4. Lint Code

```bash
# Check linting
ruff check .

# Fix linting issues
ruff check --fix .

# Type checking
mypy .
```

### 5. Commit

```bash
git add .
git commit -m "feat: description of changes"
```

Commit message format:
```
<type>: <description>

[optional body]
```

Types:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `style:` - Formatting
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Create Pull Request on GitHub.

---

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Keep functions focused and small
- Write docstrings for public functions

### Example

```python
def calculate_score(
    success_rate: float,
    response_time: float,
    weight: float = 1.0
) -> float:
    """
    Calculate provider score based on metrics.
    
    Args:
        success_rate: Success rate (0-1)
        response_time: Average response time in seconds
        weight: Weight factor
    
    Returns:
        Calculated score (higher is better)
    """
    time_score = max(0, 100 - (response_time * 10))
    return (success_rate * 0.7 + time_score * 0.3) * weight
```

---

## Testing Guidelines

### Writing Tests

- Test one thing per test function
- Use descriptive test names
- Arrange-Act-Assert pattern
- Mock external dependencies

### Example

```python
def test_classify_rate_limit_error(engine):
    """Test error classification for rate limit responses"""
    # Arrange
    error_message = "rate limit exceeded"
    status_code = 429
    
    # Act
    result = engine._classify_error(error_message, status_code)
    
    # Assert
    assert result == "rate_limit"
```

### Test Coverage

- Aim for >80% coverage on new code
- Run coverage report: `pytest tests/ --cov=. --cov-report=html`

---

## Documentation

### Types

- **Code comments**: Explain complex logic
- **Docstrings**: Public APIs
- **README**: Project overview
- **User guides**: How-to guides
- **API docs**: Endpoint documentation

### Adding Documentation

1. Update relevant markdown files
2. Add code examples
3. Include error scenarios

---

## Reporting Issues

### Bug Reports

Include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (OS, Python version)
- Error messages/logs

### Feature Requests

Include:
- Use case
- Proposed solution
- Alternatives considered

---

## Code Review

### What We Look For

- Code correctness
- Test coverage
- Documentation
- Security considerations
- Performance impact

### Responding to Review

- Address all comments
- Ask for clarification if needed
- Update PR based on feedback

---

## Release Process

1. Update version in `config.py`
2. Update CHANGELOG.md
3. Create release tag
4. Deploy to production

---

## Questions?

- Open an issue
- Start a discussion
- Check existing documentation
