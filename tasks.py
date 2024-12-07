# https://www.pyinvoke.org/

from invoke import Collection, call, task

from taskutil import (
    colorize,
    echo_on,
    find_files_and_run,
    git_repo_root,
    progress,
    uv_tool_install,
)

############################################################
# Tasks


@task
def install_json_indent(context):
    """Install json-indent tool with uv"""
    uv_tool_install(context, "json-indent")


@task
def install_mark_toc(context):
    """Install mark-toc tool with uv"""
    uv_tool_install(context, "mark-toc", constraint=">=0.5.0")


@task
def install_yamllint(context):
    """Install yamllint tool with uv"""
    uv_tool_install(context, "yamllint")


@task
def python_isort(context, fix=True):
    """Sort imports in Python source files using ruff"""
    fix_flag = "--fix" if fix else ""
    progress(python_isort, replace=not fix, replacements=("Sort ", "Check sorted ", 1))
    context.run(f"uv run ruff check --config 'lint.select = [\"I\"]' {fix_flag}")


@task
def python_lint(context, fix=False):
    """Lint Python source files using ruff"""
    fix_flag = "--fix" if fix else ""
    progress(python_lint)
    context.run(f"uv run ruff check {fix_flag}")


@task
def python_format(context, fix=True):
    """Format Python source files using ruff"""
    diff_flag = "" if fix else "--diff"
    progress(
        python_format,
        replace=not fix,
        replacements=("Format ", "Check formatting in ", 1),
    )
    context.run(f"uv run ruff format {diff_flag}")


@task(pre=[install_json_indent])
def json_indent(context):
    """Parse and format JSON files using json-indent"""
    command = "uvx json-indent --newlines=linux --pre-commit --diff '{}'"
    patterns = ["*.json"]
    progress(json_indent)
    find_files_and_run(context, command, patterns, cd=git_repo_root(context))


@task(pre=[install_mark_toc])
def mark_toc(context):
    """Generate tables-of-contents for Markdown documents using mark-toc"""
    command = "uvx mark-toc --heading-level 2 --skip-level 1 --max-level 3 --pre-commit '{}'"
    patterns = ["*.md"]
    progress(mark_toc)
    find_files_and_run(context, command, patterns, cd=git_repo_root(context))


@task(pre=[install_yamllint])
def yamllint(context):
    """Lint YAML files using yamllint"""
    progress(yamllint)
    with context.cd(git_repo_root(context)):
        context.run("uv tool run yamllint .")


@task(
    pre=[
        yamllint,
        json_indent,
        call(python_isort, fix=False),
        python_lint,
        call(python_format, fix=False),
    ]
)
def lint(context):
    """Run all lint checks"""
    pass


@task(pre=[lint, mark_toc])
def checks(context):
    """Run all checks"""
    pass


@task
def clean_docs(context):
    """Clean up documentation detritus"""
    progress(clean_docs)
    context.run("rm -r -f docs/build docs/sphinx")


@task(pre=[clean_docs])
def clean(context):
    """Clean up build and runtime detritus"""
    progress(clean)
    context.run("rm -r -f build dist")
    context.run("rm -r -f .eggs *.egg-info")
    context.run("find . -depth -type d -name '__pycache__' -exec rm -r -f '{}' ';'")
    context.run("find . -type f -name '*.py[co]' -exec rm -f '{}' ';'")


@task
def build(context, clean=False):
    """Build Python source and wheel distributions"""
    progress(build)
    context.run("uv build --no-cache")


@task(iterable=["test_name_pattern"])
def tests(context, test_name_pattern, quiet=False, failfast=False, catch=False, buffer=False):
    """Run tests using `unittest discover`"""
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
    progress(tests)
    context.run("uv run python3 -m unittest discover -s tests -t . {}".format(" ".join(args)))


@task
@echo_on
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
    """Get or bump this project's current version"""
    command = ["uv", "run", "bumpver"]
    if not bump:
        if any([major, minor, patch, release_tag, release_num]):
            raise RuntimeError("Looks like you meant to bump the version but forgot to use '--bump'")
        command.append("show")
    else:
        command.append("update")
        if not any([major, minor, patch, release_tag, release_num]):
            raise RuntimeError(
                "Looks like you want to bump the version but forgot to say what to bump"
                " (major/minor/patch/release-tag/release-num)"
            )
        if go:
            dry_run = False  # alias for --no-dry-run
        if dry_run:
            command.append("--dry")
        if major:
            command.append("--major")
        if minor:
            command.append("--minor")
        if patch:
            command.append("--patch")
        if release_tag is not None:
            if release_tag not in {"alpha", "beta", "rc", "final"}:
                raise ValueError(
                    "Only pre-releases or final releases are supported via this task; "
                    "run bumpver directly if you need more control"
                )
            command.append(f"--tag {release_tag}")
        if release_num:
            command.append("--tag-num")
    if not bump:
        description = "Get current version"
    elif dry_run:
        description = "[DRY-RUN] Would bump version"
    else:
        description = "Bump version"
    progress(description)
    context.run(" ".join(command))


############################################################
# Namespaces and visible tasks

# Non-Python checks/lint tasks
check_ns = Collection("check")
check_ns.add_task(json_indent)
check_ns.add_task(mark_toc)
check_ns.add_task(yamllint)

# Python tasks
python_ns = Collection("python")
python_ns.add_task(python_isort, name="isort")
python_ns.add_task(python_lint, name="lint")
python_ns.add_task(python_format, name="format")

# Top-level tasks
ns = Collection()  # MAGIC! Must be named `namespace` or `ns`
config_options = {
    "run": {
        # Default echo format is hard to distinguish in GitHub Actions output
        "echo_format": colorize("+ {command}", fg="blue"),
    },
}
ns.configure(config_options)

ns.add_collection(check_ns)
ns.add_collection(python_ns)

ns.add_task(lint)
ns.add_task(checks)
ns.add_task(clean_docs)
ns.add_task(clean)
ns.add_task(build)
ns.add_task(tests)
ns.add_task(version)
