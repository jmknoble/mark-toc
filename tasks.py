# https://www.pyinvoke.org/

from functools import wraps

from invoke import call, task

# fmt: off
COLOR_ATTRIBUTES = {
    "normal": 0,
    "bold"  : 1,
}

COLOR_FOREGROUNDS = {
    "black"  : 30,
    "red"    : 31,
    "green"  : 32,
    "yellow" : 33,
    "blue"   : 34,
    "magenta": 35,
    "cyan"   : 36,
    "white"  : 37,
}
# fmt: on


def colorize(text, attr=None, fg=None):
    if attr is None and fg is None:
        return text
    esc = "\033"
    attr = str(COLOR_ATTRIBUTES[attr]) + ";" if attr else ""
    fg = str(COLOR_FOREGROUNDS[fg]) if fg else ""
    reset = COLOR_ATTRIBUTES["normal"]
    prefix = f"{esc}[{attr}{fg}m"
    suffix = f"{esc}[{reset}m"
    return "".join([prefix, text, suffix])


ECHO_FORMAT = colorize("+ {command}", fg="blue")


# Workaround for https://github.com/adrienverge/yamllint/issues/700
def config(decorated_task):
    """Decorator to inject config into task context"""

    @wraps(decorated_task)
    def wrapper_func(context, *args, **kwargs):
        context.config["run"]["echo_format"] = ECHO_FORMAT
        return decorated_task(context, *args, **kwargs)

    return wrapper_func


def no_echo(decorated_task):
    """Decorator to prevent task's commands from echoing"""

    @wraps(decorated_task)
    def wrapper_func(context, *args, **kwargs):
        saved_echo_value = context.config["run"]["echo"]
        context.config["run"]["echo"] = False
        return_value = decorated_task(context, *args, **kwargs)
        context.config["run"]["echo"] = saved_echo_value
        return return_value

    return wrapper_func


def hide(decorated_task, what=True):
    """Decorator to prevent a task from showing any output"""

    if what not in {"out", "err", "both", True, None, False}:
        raise ValueError(f"@hide: what={what}: invalid value")

    @wraps(decorated_task)
    def wrapper_func(context, *args, **kwargs):
        saved_hide_value = context.config["run"]["hide"]
        context.config["run"]["hide"] = what
        return_value = decorated_task(context, *args, **kwargs)
        context.config["run"]["hide"] = saved_hide_value
        return return_value

    return wrapper_func


def hide_stdout(decorated_task):
    """Decorator to hide only a task's stdout"""
    return hide(decorated_task, what="out")


def hide_stderr(decorated_task):
    """Decorator to hide only a task's stderr"""
    return hide(decorated_task, what="err")


def progress(message, quiet=False, use_color=True):
    if quiet:
        return
    message = " ".join(["==>", message, "..."])
    if use_color:
        print(colorize(message, attr="bold", fg="green"))
    else:
        print(message)


def install_tool(context, tool, constraint=None):
    if constraint is None:
        constraint = ""
    progress(f"Installing {tool}")
    context.run(f"uv tool install '{tool}{constraint}'")


@task
@config
def install_json_indent(context):
    """Install json-indent tool with uv"""
    install_tool(context, "json-indent")


@task
@config
def install_mark_toc(context):
    """Install mark-toc tool with uv"""
    install_tool(context, "mark-toc", constraint=">=0.5.0")


@task
@config
def install_yamllint(context):
    """Install yamllint tool with uv"""
    install_tool(context, "yamllint")


@task
@hide
@config
def git_repo_root(context, default=None):
    """Get the root of the current Git repo"""
    git_command = ["git rev-parse --show-toplevel"]
    if default is not None:
        git_command.extend([f"|| echo '{default}'"])
    repo_dir = context.run(" ".join(git_command)).stdout.rsplit("\n", maxsplit=1)[0]
    return repo_dir


@task(pre=[install_yamllint])
@config
def yamllint(context):
    """Run yamllint"""
    progress("Linting YAML files with yamllint")
    with context.cd(git_repo_root(context)):
        context.run("uv tool run yamllint .")


@task
@config
def isort_python(context, fix=True):
    """Sort imports in Python source files"""
    fix_flag = "--fix" if fix else ""
    action = "Sorting" if fix else "Checking sorted"
    progress(f"{action} imports in Python source with ruff")
    context.run(f"uv run ruff check --config 'lint.select = [\"I\"]' {fix_flag}")


@task
@config
def check_python(context, fix=False):
    """Run lint checks on Python source files"""
    fix_flag = "--fix" if fix else ""
    progress("Linting Python source with ruff")
    context.run(f"uv run ruff check {fix_flag}")


@task
@config
def format_python(context, fix=True):
    """Automatically format Python source files"""
    diff_flag = "" if fix else "--diff"
    action = "Formatting" if fix else "Checking formatting in"
    progress(f"{action} Python source with ruff")
    context.run(f"uv run ruff format {diff_flag}")


@task(iterable=["patterns"])
@config
@no_echo
def find_files_and_run(context, command, patterns, cd=None):
    """Run a command on each file found matching one or more patterns"""
    full_patterns = [x.replace("'", r"'\''") for x in patterns]
    full_patterns = " ".join([f"'{x}'" for x in full_patterns])
    full_command = rf"""
git ls-files -z --cached --others --exclude-standard {full_patterns} |
xargs -0 -I '{{}}' -t {command}
""".strip("\n")
    if cd is not None:
        with context.cd(cd):
            context.run("\n" + full_command)
    else:
        context.run(full_command)


@task(pre=[install_json_indent])
@config
def format_json(context):
    """Parse and format JSON files"""
    command = "uvx json-indent --newlines=linux --pre-commit --diff '{}'"
    tool = command.replace("uvx ", "").split()[0]
    patterns = ["*.json"]
    progress(f"Parsing and formatting JSON source files with {tool}")
    find_files_and_run(context, command, patterns, cd=git_repo_root(context))


@task(pre=[install_mark_toc])
@config
def mark_toc(context):
    """Generate tables of contents for Markdown documents"""
    command = (
        "uvx mark-toc --heading-level 2 --skip-level 1 --max-level 3 --pre-commit '{}'"
    )
    tool = command.replace("uvx ", "").split()[0]
    patterns = ["*.md"]
    progress(f"Generating tables-of-contents for Markdown documents with {tool}")
    find_files_and_run(context, command, patterns, cd=git_repo_root(context))


@task(
    pre=[
        yamllint,
        format_json,
        call(isort_python, fix=False),
        check_python,
        call(format_python, fix=False),
    ]
)
@config
def lint(context):
    """Run all lint checks"""
    pass


@task(pre=[lint, mark_toc])
@config
def checks(context):
    """Run all checks"""
    pass


@task
@config
def clean_docs(context):
    """Clean up detritus from building documentation"""
    progress("Cleaning up documentation detritus")
    context.run("rm -r -f docs/build docs/sphinx")


@task(pre=[clean_docs])
@config
def clean(context):
    """Clean up build and runtime detritus"""
    progress("Cleaning up build and runtime detritus")
    context.run("rm -r -f build dist")
    context.run("rm -r -f .eggs *.egg-info")
    context.run("find . -depth -type d -name '__pycache__' -exec rm -r -f '{}' ';'")
    context.run("find . -type f -name '*.py[co]' -exec rm -f '{}' ';'")


@task
@config
def build(context, clean=False):
    """Build Python source and wheel distributions"""
    progress("Building Python distributions")
    context.run("uv build --no-cache")


@task(iterable=["test_name_pattern"])
@config
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
    progress("Running tests")
    context.run(
        "uv run python3 -m unittest discover -s tests -t . {}".format(" ".join(args))
    )


@task
@config
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
    if not bump:
        action = "Getting"
    elif dry_run:
        action = "Would bump"
    else:
        action = "Bumping"
    progress(f"{action} version")
    context.run("uv run bumpver {}".format(" ".join(args)))
