# https://www.pyinvoke.org/
from invoke import call, task


@task
def install_mark_toc(context):
    """Install mark-toc tool with uv"""
    context.run("uv tool install mark-toc")


@task
def install_yamllint(context):
    """Install yamllint tool with uv"""
    context.run("uv tool install yamllint")


@task(pre=[install_yamllint])
def yamllint(context):
    """Run yamllint"""
    context.run("uv tool run yamllint .")


@task
def isort_python(context, fix=True):
    """Sort imports in Python source files"""
    fix_flag = "--fix" if fix else ""
    context.run(f"uv run ruff check --config 'lint.select = [\"I\"]' {fix_flag}")


@task
def check_python(context, fix=False):
    """Run lint checks on Python source files"""
    fix_flag = "--fix" if fix else ""
    context.run(f"uv run ruff check {fix_flag}")


@task
def format_python(context, fix=True):
    """Automatically format Python source files"""
    diff_flag = "" if fix else "--diff"
    context.run(f"uv run ruff format {diff_flag}")


@task(
    pre=[
        yamllint,
        call(isort_python, fix=False),
        check_python,
        call(format_python, fix=False),
    ]
)
def lint(context):
    """Run all lint checks"""
    pass


@task(pre=[install_mark_toc])
def mark_toc(context):
    """Generate tables of contents for Markdown documents"""
    context.run(r"""
find . \( \
    -type d \
    \( -name .git -o -name .ruff_cache -o -name .venv \) \
    -prune \
\) -o \( \
    -type f \
    -name '*.md' \
    -exec uvx mark-toc --heading-level 2 --skip-level 1 --pre-commit '{}' ';' \
\)
""")


@task(pre=[lint, mark_toc])
def checks(context):
    """Run all checks"""
    pass


@task
def clean_docs(context):
    """Clean up documentation artifacts"""
    context.run("rm -r -f docs/build docs/sphinx")


@task(pre=[clean_docs])
def clean(context):
    """Clean up build artifacts, etc."""
    context.run("rm -r -f build dist")
    context.run("rm -r -f .eggs *.egg-info")
    context.run("find . -depth -type d -name '__pycache__' -exec rm -r -f '{}' ';'")
    context.run("find . -type f -name '*.py[co]' -exec rm -f '{}' ';'")


@task
def build(context, clean=False):
    """Build Python source and wheel distributions"""
    context.run("uv build --no-cache")


@task(iterable=["test_name_pattern"])
def tests(
    context, test_name_pattern, quiet=False, failfast=False, catch=False, buffer=False
):
    """Run tests using `python3 -m unittest discover`"""
    args = []
    args.append("-q" if quiet else "-v")
    if failfast:
        args.append("--failfast")
    if catch:
        args.append("--catch")
    if buffer:
        args.append("--buffer")
    if test_name_pattern:
        args.append("-k")
        args.extend(test_name_pattern)
    context.run(
        "uv run python3 -m unittest discover -s tests -t . {}".format(" ".join(args))
    )


@task
def version(
    context,
    bump=False,
    dry_run=True,
    go=False,
    release_tag=None,
    release_num=False,
    patch=False,
    minor=False,
    major=False,
):
    """Show or update this project's current version"""
    args = []
    if not bump:
        if any([major, minor, patch, release_tag, release_num]):
            raise RuntimeError(
                "Looks like you meant to bump the version but forgot to use '--bump'"
            )
        args.append("show")
    else:
        args.append("update")
        if go:
            dry_run = False  # alias for --no-dry-run
        if dry_run:
            args.append("--dry")
        if major:
            args.append("--major")
        if minor:
            args.append("--minor")
        if patch:
            args.append("--patch")
        if release_tag is not None:
            if release_tag not in {"alpha", "beta", "rc", "final"}:
                raise ValueError(
                    "Only pre-releases or final releases are supported via this task; "
                    "run bumpver directly if you need more control"
                )
            args.append(f"--tag {release_tag}")
        if release_num:
            args.append("--tag-num")
    context.run("uv run bumpver {}".format(" ".join(args)))
