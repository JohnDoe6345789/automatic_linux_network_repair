# Justfile for automatic_linux_network_repair

# Show available commands
list:
    @just --list

# Run all the formatting, linting, and testing commands
qa:
    poetry run ruff format .
    poetry run ruff check . --fix
    poetry run ruff check --select I --fix .
    poetry run ty check .
    poetry run pytest .

# Run all the tests for the currently configured Python environment
# (multi-version testing is handled in CI via the GitHub Actions matrix)
testall:
    poetry run pytest .

# Run all the tests, but allow for arguments to be passed
test *ARGS:
    @echo "Running with arg: {{ARGS}}"
    poetry run pytest {{ARGS}}

# Run all the tests, but on failure, drop into the debugger
pdb *ARGS:
    @echo "Running with arg: {{ARGS}}"
    poetry run pytest --pdb --maxfail=10 --pdbcls=IPython.terminal.debugger:TerminalPdb {{ARGS}}

# Run coverage, and build to HTML
coverage:
    poetry run coverage run -m pytest .
    poetry run coverage report -m
    poetry run coverage html

# Build the project, useful for checking that packaging is correct
build:
    rm -rf build
    rm -rf dist
    poetry build

VERSION := `poetry version -s`

# Print the current version of the project
version:
    @echo "Current version is {{VERSION}}"

# Tag the current version in git and push to GitHub
tag:
    echo "Tagging version v{{VERSION}}"
    git tag -a v{{VERSION}} -m "Creating version v{{VERSION}}"
    git push origin v{{VERSION}}

# remove all build, test, coverage and Python artifacts
clean: 
	clean-build
	clean-pyc
	clean-test

# remove build artifacts
clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

# remove Python file artifacts
clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

# remove test and coverage artifacts
clean-test:
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
