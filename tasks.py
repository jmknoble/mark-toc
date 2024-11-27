# https://www.pyinvoke.org/

from copy import deepcopy
from functools import wraps

from invoke import call, task

########################################
# Utility functions

ATTRIBUTE_NAMES = ["normal", "bold"]
COLOR_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
ATTRIBUTES = {x: i for (i, x) in enumerate(ATTRIBUTE_NAMES)}
FOREGROUNDS = {x: i + 30 for (i, x) in enumerate(COLOR_NAMES)}
BACKGROUNDS = {x: i + 40 for (i, x) in enumerate(COLOR_NAMES)}


def color_code(name, lookup):
    return "" if not name else str(lookup[name])


def color_codes(attr, fg, bg):
    codes = []
    for code in [
        color_code(attr, ATTRIBUTES),
        color_code(fg, FOREGROUNDS),
        color_code(bg, BACKGROUNDS),
    ]:
        if code:
            codes.append(code)
    return ";".join(codes)


def color_escape_sequence(attr, fg, bg):
    return "".join(["\033[", color_codes(attr, fg, bg), "m"])


def colorize(text, attr=None, fg=None, bg=None):
    if not any([attr, fg, bg]):
        return text
    prefix = color_escape_sequence(attr, fg, bg)
    suffix = color_escape_sequence("normal", None, None)
    return "".join([prefix, text, suffix])


def print_progress(message, quiet=False, use_color=True):
    if quiet:
        return
    message = " ".join(["==>", message, "..."])
    if use_color:
        print(colorize(message, attr="bold", fg="green"))
    else:
        print(message)


def progress(func_or_message, replace=False, replacements=None):
    if isinstance(func_or_message, str):
        message = func_or_message
    else:
        try:
            message = func_or_message.__doc__
        except AttributeError:
            message = func_or_message
    if replace and replacements:
        message = message.replace(*replacements)
    print_progress(message)


def sparse_update_dict(target, subdict, copy=True):
    for key1 in subdict:
        if isinstance(subdict[key1], dict):
            sparse_update_dict(target[key1], subdict[key1])  # recursive
        elif copy:
            try:
                target[key1] = subdict[key1].copy()
            except AttributeError:
                target[key1] = subdict[key1]
        else:
            target[key1] = subdict[key1]


########################################
# Decorators


def taskconfig(decorated_task, config_dict=None, restore=True):
    """Decorator to inject config into task context"""

    @wraps(decorated_task)
    def wrapper_func(context, *args, **kwargs):
        if config_dict:
            if restore:
                saved_config = context.config
                new_config = deepcopy(context.config)
                context.config = new_config
            sparse_update_dict(context.config, config_dict)
        return_value = decorated_task(context, *args, **kwargs)
        if config_dict and restore:
            context.config = saved_config
        return return_value

    return wrapper_func


# Workaround for https://github.com/adrienverge/yamllint/issues/700
def config(decorated_task):
    """Decorator to inject config into task context"""
    return taskconfig(
        decorated_task,
        config_dict={"run": {"echo_format": colorize("+ {command}", fg="blue")}},
        restore=False,
    )


def no_echo(decorated_task):
    """Decorator to prevent task's commands from echoing"""
    return taskconfig(decorated_task, config_dict={"run": {"echo": False}})


def always_echo(decorated_task):
    """Decorator to prevent task's commands from echoing"""
    return taskconfig(decorated_task, config_dict={"run": {"echo": True}})


def hide(decorated_task, what=True):
    """Decorator to prevent a task from showing any output"""
    if what not in {"out", "stdout", "err", "stderr", "both", True, None, False}:
        raise ValueError(f"@hide: what={what}: invalid value")
    return taskconfig(decorated_task, config_dict={"run": {"hide": what}})


def hide_stdout(decorated_task):
    """Decorator to hide only a task's stdout"""
    return hide(decorated_task, what="stdout")


def hide_stderr(decorated_task):
    """Decorator to hide only a task's stderr"""
    return hide(decorated_task, what="stderr")


########################################
# Tasks


def install_tool(context, tool, constraint=None):
    if constraint is None:
        constraint = ""
    progress(f"Install {tool}")
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
@config
def git_repo_root(context, default=None, quiet=False):
    """Get the root of the current Git repo"""
    git_command = ["git rev-parse --show-toplevel"]
    if default is not None:
        git_command.extend([f"|| echo '{default}'"])
    repo_dir = context.run(" ".join(git_command), hide=quiet).stdout.rsplit(
        "\n", maxsplit=1
    )[0]
    return repo_dir


@task(pre=[install_yamllint])
@config
def yamllint(context):
    """Lint YAML files using yamllint"""
    progress(yamllint)
    with context.cd(git_repo_root(context, quiet=True)):
        context.run("uv tool run yamllint .")


@task
@config
def isort_python(context, fix=True):
    """Sort imports in Python source files using ruff"""
    fix_flag = "--fix" if fix else ""
    progress(isort_python, replace=not fix, replacements=("Sort ", "Check sorted ", 1))
    context.run(f"uv run ruff check --config 'lint.select = [\"I\"]' {fix_flag}")


@task
@config
def check_python(context, fix=False):
    """Lint Python source files using ruff"""
    fix_flag = "--fix" if fix else ""
    progress(check_python)
    context.run(f"uv run ruff check {fix_flag}")


@task
@config
def format_python(context, fix=True):
    """Format Python source files using ruff"""
    diff_flag = "" if fix else "--diff"
    progress(
        format_python,
        replace=not fix,
        replacements=("Format ", "Check formatting in ", 1),
    )
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
    """Parse and format JSON files using json-indent"""
    command = "uvx json-indent --newlines=linux --pre-commit --diff '{}'"
    patterns = ["*.json"]
    progress(format_json)
    find_files_and_run(
        context, command, patterns, cd=git_repo_root(context, quiet=True)
    )


@task(pre=[install_mark_toc])
@config
def mark_toc(context):
    """Generate tables-of-contents for Markdown documents using mark-toc"""
    command = (
        "uvx mark-toc --heading-level 2 --skip-level 1 --max-level 3 --pre-commit '{}'"
    )
    patterns = ["*.md"]
    progress(mark_toc)
    find_files_and_run(
        context, command, patterns, cd=git_repo_root(context, quiet=True)
    )


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
    """Clean up documentation detritus"""
    progress(clean_docs)
    context.run("rm -r -f docs/build docs/sphinx")


@task(pre=[clean_docs])
@config
def clean(context):
    """Clean up build and runtime detritus"""
    progress(clean)
    context.run("rm -r -f build dist")
    context.run("rm -r -f .eggs *.egg-info")
    context.run("find . -depth -type d -name '__pycache__' -exec rm -r -f '{}' ';'")
    context.run("find . -type f -name '*.py[co]' -exec rm -f '{}' ';'")


@task
@config
def build(context, clean=False):
    """Build Python source and wheel distributions"""
    progress(build)
    context.run("uv build --no-cache")


@task(iterable=["test_name_pattern"])
@config
def tests(
    context, test_name_pattern, quiet=False, failfast=False, catch=False, buffer=False
):
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
    context.run(
        "uv run python3 -m unittest discover -s tests -t . {}".format(" ".join(args))
    )


@task
@config
@always_echo
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
    args = []
    if not bump:
        if any([major, minor, patch, release_tag, release_num]):
            raise RuntimeError(
                "Looks like you meant to bump the version but forgot to use '--bump'"
            )
        args.append("show")
    else:
        args.append("update")
        if not any([major, minor, patch, release_tag, release_num]):
            raise RuntimeError(
                "Looks like you want to bump the version but forgot to say what to bump"
                " (major/minor/patch/release-tag/release-num)"
            )
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
        description = "Get current version"
    elif dry_run:
        description = "[DRY-RUN] Would bump version"
    else:
        description = "Bump version"
    progress(description)
    context.run("uv run bumpver {}".format(" ".join(args)))
