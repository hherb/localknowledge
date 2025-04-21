# Contributing Guidelines

## Overview

Thank you for considering contributing to the Local Knowledge project! This document provides guidelines for contributing to the project, including coding standards, commit message format, and the pull request process.

## Getting Started

### Setting Up the Development Environment

Before you start contributing, set up your development environment:

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment as described in [Development Setup](development-setup.md)
4. Create a new branch for your changes

### Finding Issues to Work On

You can find issues to work on in the project's issue tracker. Issues labeled "good first issue" are a good place to start for new contributors.

## Coding Standards

### Python Style Guide

The project follows the [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide for Python code. Some key points:

- Use 4 spaces for indentation (not tabs)
- Use snake_case for variable and function names
- Use CamelCase for class names
- Keep lines under 100 characters
- Use docstrings for functions, classes, and modules

### Documentation

All code should be documented:

- Use docstrings for functions, classes, and modules
- Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for docstring format
- Update relevant documentation when making changes

Example docstring:

```python
def example_function(param1, param2):
    """
    Example function that does something.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: Description of when this exception is raised
    """
    # Implementation
    return result
```

### Testing

All code should be tested:

- Write unit tests for new functionality
- Update tests for modified functionality
- Ensure all tests pass before submitting a pull request

## Git Workflow

### Branching Model

The project uses a feature branch workflow:

- `master` branch is the main development branch
- Feature branches are created from `master` for new features or bug fixes
- Pull requests are submitted to merge feature branches into `master`

### Commit Messages

Commit messages should be clear and descriptive:

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests where appropriate

Example commit message:

```
Add keyword extraction using PyTextRank

- Implement PyTextRank-based keyword extraction
- Add tests for keyword extraction
- Update documentation

Fixes #123
```

### Pull Requests

When submitting a pull request:

1. Update the documentation to reflect your changes
2. Update the tests to cover your changes
3. Ensure all tests pass
4. Fill in the pull request template
5. Reference any related issues

## Development Process

### Feature Development

When developing a new feature:

1. Create a new branch from `master`
2. Implement the feature with tests and documentation
3. Submit a pull request to merge the feature branch into `master`

### Bug Fixes

When fixing a bug:

1. Create a new branch from `master`
2. Write a test that reproduces the bug
3. Fix the bug
4. Ensure the test passes
5. Submit a pull request to merge the bug fix branch into `master`

### Code Review

All code changes are reviewed before merging:

- Code reviews focus on code quality, correctness, and adherence to standards
- Address all review comments before the pull request is merged
- Be respectful and constructive in code review discussions

## Project Structure

Understanding the project structure helps when contributing:

```
localknowledge/
├── ai/                 # AI functionality
├── db/                 # Database functionality
├── textprocessing/     # Text processing functionality
├── ui/                 # User interface functionality
├── medrxiv/            # MedRxiv-specific functionality
├── pubmed/             # PubMed-specific functionality
└── tests/              # Tests
```

When adding new functionality, follow the existing structure and patterns.

## Communication

### Issue Tracker

Use the issue tracker for:

- Reporting bugs
- Requesting features
- Tracking work in progress

When creating an issue:

- Use a clear and descriptive title
- Provide detailed steps to reproduce bugs
- Include expected and actual behavior
- Include screenshots or logs if relevant

### Discussions

Use discussions for:

- Asking questions
- Proposing ideas
- Discussing implementation details

Be respectful and constructive in all communications.

## Release Process

The project follows a regular release schedule:

1. Features and bug fixes are merged into `master`
2. When ready for release, a release branch is created
3. Final testing and documentation updates are done on the release branch
4. A release is tagged and published

## License

By contributing to the project, you agree that your contributions will be licensed under the project's license.

## Code of Conduct

Please follow the project's code of conduct in all interactions.

## FAQ

### How do I report a bug?

Create an issue in the issue tracker with a clear description of the bug, steps to reproduce, and expected behavior.

### How do I request a feature?

Create an issue in the issue tracker with a clear description of the feature and its benefits.

### How do I submit a pull request?

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request to the `master` branch

### How do I run the tests?

```bash
# Run all tests
pytest

# Run specific tests
pytest localknowledge/tests/test_embeddings.py
```

### How do I update the documentation?

1. Update docstrings in the code
2. Update markdown files in the `manual` directory
3. Submit a pull request with your changes

## Acknowledgments

Thank you to all contributors who help improve the Local Knowledge project!
