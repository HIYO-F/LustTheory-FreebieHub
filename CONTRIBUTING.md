# Contributing to WHEN Language

We welcome contributions to the WHEN language! This document outlines how to contribute effectively.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/when-lang.git
   cd when-lang
   ```
3. **Create a branch** for your feature:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

1. **Install in development mode:**
   ```bash
   pip install -e ".[dev]"
   ```

2. **Test the installation:**
   ```bash
   when --version
   when examples/clock.when
   ```

## Types of Contributions

### 🐛 Bug Reports
- Use the issue tracker with a clear description
- Include steps to reproduce
- Provide the WHEN code that causes the issue
- Mention your Python version and OS

### ✨ Feature Requests
- Describe the feature and its use case
- Explain how it fits with WHEN's philosophy
- Consider proposing the syntax if it's a language feature

### 🔧 Code Contributions

#### Language Features
- **Lexer** (`lexer.py`) - New keywords, operators, syntax
- **Parser** (`parser.py`) - Grammar rules, AST nodes
- **Interpreter** (`interpreter.py`) - Runtime behavior, built-ins
- **AST** (`ast_nodes.py`) - New node types

#### Examples and Documentation
- **Examples** (`examples/`) - Show off language features
- **Documentation** (`docs/`) - Language reference, tutorials
- **README** improvements

#### Tools and Infrastructure
- **CLI** (`when.py`) - Command-line interface improvements
- **Testing** - Unit tests, integration tests
- **Performance** - Optimizations, benchmarks

## Coding Standards

### Python Code Style
- Follow PEP 8
- Use type hints where helpful
- Keep functions focused and small
- Add docstrings for public APIs

### WHEN Language Style
- Use clear, descriptive variable names
- Prefer `when` conditions over complex logic
- Comment complex block interactions
- Follow the examples' style

### Example Format
```when
# Brief description of what this example demonstrates
import math  # If needed

# Variables with clear names
counter = 0
active = 1

# Functions for reusable logic
def calculate_something(x):
    return x * 2

# Blocks with clear purposes
os setup():
    print("Example: Description")
    print("Purpose: What this shows")

de timer(5):
    counter = counter + 1
    print("Step", counter)

fo monitor():
    when counter >= 3:
        print("Halfway!")

# Clear main logic
main:
    when active == 1:
        setup()
        timer.start()
        monitor.start()
        active = 0

    when counter >= 5:
        print("Example complete!")
        timer.stop()
        monitor.stop()
        exit()
```

## Testing

### Running Tests
```bash
# Install test dependencies
pip install -e ".[dev]"

# Run tests (when we add them)
pytest

# Test specific examples
when examples/clock.when
when examples/traffic_light.when
```

### Writing Tests
- Add test files to `tests/` directory
- Test both positive and negative cases
- Include edge cases and error conditions
- Test examples to ensure they work

## Language Design Philosophy

When contributing language features, consider WHEN's core principles:

1. **Loop-Centric**: Everything happens in implicit loops
2. **Reactive**: `when` conditions drive execution
3. **Explicit Lifecycle**: Clear `.start()` and `.stop()` control
4. **Cooperative**: No hidden threading complexity
5. **Pythonic**: Leverage Python's ecosystem and familiarity

### Good Feature Examples:
- New block types (like `parallel fo`)
- Built-in functions for common patterns
- Syntax sugar for WHEN idioms
- Better error messages

### Features to Avoid:
- Complex threading abstractions
- Non-cooperative concurrency
- Breaking the loop paradigm
- Unnecessary syntax complexity

## Pull Request Process

1. **Update documentation** if you change language features
2. **Add examples** demonstrating new functionality
3. **Test thoroughly** with various WHEN programs
4. **Write clear commit messages**:
   ```
   feat: add parallel blocks for true concurrency

   - Adds `parallel fo` and `parallel de` block types
   - Implements thread-safe execution
   - Updates parser and interpreter
   - Includes example: parallel_demo.when
   ```

5. **Open a pull request** with:
   - Clear description of changes
   - Examples of new functionality
   - Screenshots if it affects output
   - Links to related issues

## Community Guidelines

- **Be respectful** and constructive
- **Help newcomers** learn WHEN
- **Share interesting programs** you've written
- **Discuss ideas** before implementing major changes
- **Credit others** for inspiration and help

## Questions?

- **Issues**: Use GitHub Issues for bugs and features
- **Discussions**: Use GitHub Discussions for general questions
- **Examples**: Share cool WHEN programs in discussions

Thank you for contributing to WHEN! 🎉