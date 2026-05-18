# Contributing to DocFormatConverter

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/badhope/DocFormatConverter.git
cd DocFormatConverter
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

## Running Tests

```bash
pytest
pytest --cov=src tests/
```

## Code Style

```bash
black src/ tests/
flake8 src/ tests/
mypy src/
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
