# Contributing to DTAT OCR

Thank you for your interest in contributing to DTAT OCR! This document provides guidelines and information for contributors.

## Getting Started

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/NotADevIAmaMeatPopsicle/DTAT-OCR.git
   cd DTAT-OCR
   ```

2. Create a virtual environment:
   ```bash
   uv venv --python 3.12 --seed
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

4. Initialize the database:
   ```bash
   python worker.py init
   ```

5. Run the development server:
   ```bash
   python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
   ```

### Running Tests

```bash
# Process a test document
python worker.py process samples/sample_paper.pdf --json

# Check system health
curl http://localhost:8000/health
```

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/NotADevIAmaMeatPopsicle/DTAT-OCR/issues)
2. If not, create a new issue with:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - System information (OS, Python version, GPU if applicable)

### Suggesting Features

1. Open an issue with the "enhancement" label
2. Describe the feature and its use case
3. Discuss implementation approach if you have ideas

### Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test your changes thoroughly
5. Commit with clear messages: `git commit -m "Add feature X"`
6. Push to your fork: `git push origin feature/my-feature`
7. Open a Pull Request

### Pull Request Guidelines

- Keep PRs focused on a single change
- Update documentation if needed
- Add tests for new functionality
- Ensure all existing tests pass
- Follow the existing code style

## Architecture Decision Records (ADRs)

For significant architectural changes, please:

1. Read existing ADRs in `docs/adr/`
2. Create a new ADR using `docs/adr/template.md`
3. Include the ADR in your PR for discussion

## Code Style

- Follow PEP 8 for Python code
- Use type hints where practical
- Keep functions focused and documented
- Prefer clarity over cleverness

## Licensing

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to open an issue for any questions about contributing.
