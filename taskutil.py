from copy import deepcopy
from functools import wraps

############################################################
# Colorization

ATTRIBUTE_NAMES = ["normal", "bold"]
COLOR_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
ATTRIBUTES = {x: i for (i, x) in enumerate(ATTRIBUTE_NAMES)}
FOREGROUNDS = {x: i + 30 for (i, x) in enumerate(COLOR_NAMES)}
BACKGROUNDS = {x: i + 40 for (i, x) in enumerate(COLOR_NAMES)}


def _color_code(name, lookup):
    """Return an ANSI color or attribute code for the given name"""
    return "" if not name else str(lookup[name])


def _color_codes(attr, fg, bg):
    """Return ANSI codes for the given attribute/colors, joined in a string"""
    codes = []
    for code in [
        _color_code(attr, ATTRIBUTES),
        _color_code(fg, FOREGROUNDS),
        _color_code(bg, BACKGROUNDS),
    ]:
        if code:
            codes.append(code)
    return ";".join(codes)


def _color_escape_sequence(attr, fg, bg):
    """Return ANSI escape sequence with codes for the givven attribute/colors"""
    return "".join(["\033[", _color_codes(attr, fg, bg), "m"])


def colorize(text, attr=None, fg=None, bg=None):
    """Return text wrapped with ANSI color/attribute codes"""
    if not any([attr, fg, bg]):
        return text
    prefix = _color_escape_sequence(attr, fg, bg)
    suffix = _color_escape_sequence("normal", None, None)
    return "".join([prefix, text, suffix])


############################################################
# Print colorized progress messages from tasks


def print_progress(message, quiet=False, use_color=True):
    """Print a progress message"""
    if quiet:
        return
    message = " ".join(["==>", message, "..."])
    if use_color:
        print(colorize(message, attr="bold", fg="green"))
    else:
        print(message)


def progress(func_or_message, replace=False, replacements=None):
    """Print a progress message that defaults to a function's docstring"""
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


############################################################
# Utility functions


def _sparse_update_dict(target, subdict, copy=True):
    """Update `target` dict tree from sparse `subdict`, leaving unmentioned values intact"""
    for key1 in subdict:
        if isinstance(subdict[key1], dict):
            _sparse_update_dict(target[key1], subdict[key1])  # recursive
        elif copy:
            try:
                target[key1] = subdict[key1].copy()
            except AttributeError:
                target[key1] = subdict[key1]
        else:
            target[key1] = subdict[key1]


############################################################
# Decorators


def set_taskconfig(decorated_task, config_dict=None, restore=True):
    """Base decorator: Inject config from `config_dict` into task context"""

    @wraps(decorated_task)
    def wrapper_func(context, *args, **kwargs):
        if config_dict:
            if restore:
                saved_config = context.config
                new_config = deepcopy(context.config)
                context.config = new_config
            _sparse_update_dict(context.config, config_dict)
        return_value = decorated_task(context, *args, **kwargs)
        if config_dict and restore:
            context.config = saved_config
        return return_value

    return wrapper_func


# Workaround for https://github.com/adrienverge/yamllint/issues/700
def extend_config(decorated_task):
    """Decorator: Inject specific 'default' config into wrapped task's context"""
    return set_taskconfig(
        decorated_task,
        config_dict={"run": {"echo_format": colorize("+ {command}", fg="blue")}},
        restore=False,
    )


def echo_off(decorated_task):
    """Decorator: Prevent task's commands from echoing"""
    return set_taskconfig(decorated_task, config_dict={"run": {"echo": False}})


def echo_on(decorated_task):
    """Decorator: Force task's commands to echo"""
    return set_taskconfig(decorated_task, config_dict={"run": {"echo": True}})


def hide(decorated_task, what=True):
    """Decorator: Prevent a task from showing stdout and/or stderr (default: both)"""
    if what not in {"out", "stdout", "err", "stderr", "both", True, None, False}:
        raise ValueError(f"@hide: what={what}: invalid value")
    return set_taskconfig(decorated_task, config_dict={"run": {"hide": what}})


def hide_stdout(decorated_task):
    """Decorator: Hide only a task's stdout"""
    return hide(decorated_task, what="stdout")


def hide_stderr(decorated_task):
    """Decorator: Hide only a task's stderr"""
    return hide(decorated_task, what="stderr")
