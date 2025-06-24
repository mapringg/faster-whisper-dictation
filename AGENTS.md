## Build, Lint, and Test Commands

- **Run the application**: `./run.sh`
- **Install/update dependencies**: `pip install .`
- **Linting**: `ruff check .`
- **Formatting**: `ruff format .`
- **Testing**: No dedicated test suite found. Create unit tests in a `tests/` directory and use `pytest`.

## Code Style Guidelines

- **Formatting**: Use `ruff format` with 4-space indentation and double quotes.
- **Imports**: Group imports and sort them using `ruff`.
- **Naming**: Use `snake_case` for variables and functions, `PascalCase` for classes.
- **Types**: Add type hints to all function definitions.
- **Error Handling**: Use `try...except` blocks for error handling and log exceptions.
- **Logging**: Use the `logging` module for logging.
- **Environment Variables**: Store secrets and configuration in a `.env` file.
