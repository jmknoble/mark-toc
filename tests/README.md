# Unit tests

Add unit tests in a well-structured folder tree here.

> [!TIP]
>
> Commonly, unit tests for `src/package/module.py` are placed in `tests/package/test_module.py` or
> `tests/test_package/test_module.py`.


## Unit test frameworks

If you use [unittest][] for your unit testing framework, it's part of Python's "batteries included".
You can run tests based on `unittest` using:

    uv run invoke tests

For other unit test frameworks, such as [pytest][], you'll likely need to add them to the project as
development dependencies.  For example:

    uv add --dev pytest


## Excluding tests from builds

By default, [pyproject.toml][] is configured to exclude everything under the `tests` folder from
Python source distributions, using `[tool.hatch.build.targets.sdist]` > `exclude`.
This automatically excludes them from binary wheel distributions as well.

If you prefer to place your tests elsewhere, or prefer to include your tests in source
distributions, you'll probably need to change the `exclude` (and possibly `include`) settings.


## Linting tests with ruff

Depending on the test framework and the requirements of the tests, the lint rules for tests may need
to differ from the rules for the main code base.  These rules can be configured in a [.ruff.toml][]
file at the top of the directory tree they apply to.

See [Ruff's configuration documentation][ruff-doc-config] for more info.


 [pyproject.toml]: ../pyproject.toml
 [.ruff.toml]: .ruff.toml

 [pytest]: pytest.org
 [ruff-doc-config]: https://docs.astral.sh/ruff/configuration/
 [unittest]: https://docs.python.org/3/library/unittest.html
