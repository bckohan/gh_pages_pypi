# Contributing

Contributions are encouraged! Please use the issue page to submit feature requests or bug reports. Issues with attached PRs will be given priority and have a much higher likelihood of acceptance. Please also open an issue and associate it with any submitted PRs. Before PRs can be merged all added code test coverage must be 100%.

We are actively seeking additional maintainers. If you're interested, please open an issue or [contact me](https://github.com/bckohan).

## Installation

### Install Just

We provide a platform independent justfile with recipes for all the development tasks. You should [install just](https://just.systems/man/en/installation.html) if it is not on your system already.

``ghr-pypi`` uses [uv](https://docs.astral.sh/uv) for environment, package, and dependency management. ``just setup`` will install the necessary build tooling if you do not already have it:

```sh
just setup <python version>
```

**This will also install prek** If you wish to submit code that does not pass pre-commit checks you can disable [prek](https://prek.j178.dev) by running:

```sh
just run prek uninstall
```

### Install the Dev environment

To install all development dependencies run the ``install`` recipe:

```sh
just install
```

## Documentation

`ghr-pypi` documentation is generated using [Sphinx](https://www.sphinx-doc.org) with the [furo](https://github.com/pradyunsg/furo) theme. Any new feature PRs must provide updated documentation for the features added. To build the docs run doc8 to check for formatting issues then run Sphinx:

```sh
just docs  # builds docs
just check-docs  # lint the docs
just check-docs-links  # check for broken links in the docs
```

Run the docs with auto rebuild using:

```sh
just docs-live
```

## Static Analysis

`ghr-pypi` uses [ruff](https://docs.astral.sh/ruff/) for Python linting, header import standardization and code formatting. [mypy](http://mypy-lang.org/) and [pyright](https://github.com/microsoft/pyright) are used for static type checking. Before any PR is accepted the following must be run, and static analysis tools should not produce any errors or warnings. Disabling certain errors or warnings where justified is acceptable:

To fix formatting and linting problems that are fixable run:

```sh
just fix
```

To run all static analysis without automated fixing you can run:

```sh
just check
```

## Running Tests

`ghr-pypi` is set up to use [pytest](https://docs.pytest.org) to run unit tests. All the tests are housed in `tests`. Before a PR is accepted, all tests must be passing and the code coverage must be at 100%. A small number of exempted error handling branches are acceptable.

To run the full suite:

```shell
just test
```

To run a single test, or group of tests in a class:

```shell
just test <path_to_tests_file>::ClassName::FunctionName
```

### Debugging tests

To debug a test use the ``debug-test`` recipe:

```shell
just debug-test <path_to_tests_file>::ClassName::FunctionName
```

This will set a breakpoint at the start of the test.

## Versioning

`ghr-pypi` uses [CalVer](https://calver.org): `YYYY.M.D`, with a
`.N` serial suffix for repeat releases on the same day. The tool and the demo
packages always share the release version.

## Issuing Releases

The release workflow is triggered by tag creation. You must have [git tag signing enabled](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits). Our justfile has a release shortcut — it must be run from a clean `main` checkout, and it runs the full check suite, stamps every package, commits, signs the tag, and pushes:

```sh
just release
```

## Just Recipes

Run just with no recipe to see a list of all available commands:

```sh
just
```

```sh
bandit                       # run bandit static security analysis
build                        # build docs and package
build-docs                   # build the docs
build-docs-html              # build html documentation
check *ENV                   # run all static checks
check-all *ENV               # run all checks including documentation link checking (slow)
check-docs *ENV              # lint the documentation
check-docs-links             # check documentation links for broken links
check-format *ENV            # check if the code needs formatting
check-lint *ENV              # lint the code
check-package                # run package checks
check-readme *ENV            # check that the readme renders
check-types *ENV             # run all static type checking
check-types-isolated *ENV    # run all static type checking in an isolated environment
check-types-mypy *ENV        # run static type checking with mypy
check-types-pyright *ENV     # run static type checking with pyright
clean                        # remove all non-repository artifacts
clean-docs                   # remove doc build artifacts
clean-env                    # remove the virtual environment
clean-git-ignored            # remove all git ignored files
coverage                     # generate the test coverage report
coverage-erase               # erase any coverage data
debug-test *TESTS            # debug a test
docs                         # build and open the documentation
docs-live                    # serve the documentation with auto-reload
fetch-refs LIB               # fetch intersphinx references for the given package
fix *ENV                     # fix formatting, linting issues and import sorting
format *ENV                  # format the code and sort imports
format-workflows             # format the github workflow files
install *OPTS="--all-extras" # update and install development dependencies
install-prek                 # install git pre-commit hooks
install-uv                   # install the uv package manager
lint *ENV                    # sort imports and fix linting issues
open-docs                    # open the html documentation
prek                         # run the pre-commit checks
release                      # CalVer-release the repo: stamp all packages, test, commit, sign tag, push — triggers release.yml
run +ARGS                    # run the command in the virtual environment
setup python="python"        # setup the venv and pre-commit hooks
sort-imports *ENV            # sort the python imports
test *TESTS                  # run specific tests (project venv)
test-all *ENV                # run all tests in an isolated environment (pass any uv run flags, e.g. -p 3.13)
validate_version VERSION     # validate the given version tag against every package version site
zizmor                       # run zizmor security analysis of CI
```
