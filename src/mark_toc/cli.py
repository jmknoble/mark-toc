"""Make table of contents in Markdown files."""

from __future__ import print_function

import datetime
import difflib
import os.path
import sys

import argcomplete

from . import argparsing, completion, get_version, iofile, mdfile

####################

STATUS_SUCCESS = 0
STATUS_FAILURE = 1
STATUS_CHANGED = 99

DIFF_CONTEXT_LINES = 3

NEWLINE_FORMAT_LINUX = "linux"
NEWLINE_FORMAT_MICROSOFT = "microsoft"
NEWLINE_FORMAT_NATIVE = "native"

NEWLINE_FORMATS = [
    NEWLINE_FORMAT_LINUX,
    NEWLINE_FORMAT_MICROSOFT,
    NEWLINE_FORMAT_NATIVE,
]

NEWLINE_FORMAT_ALIAS_DOS = "dos"
NEWLINE_FORMAT_ALIAS_MACOS = "macos"
NEWLINE_FORMAT_ALIAS_MSFT = "msft"
NEWLINE_FORMAT_ALIAS_UNIX = "unix"
NEWLINE_FORMAT_ALIAS_WINDOWS = "windows"

NEWLINE_FORMAT_ALIASES = {
    NEWLINE_FORMAT_ALIAS_DOS: NEWLINE_FORMAT_MICROSOFT,
    NEWLINE_FORMAT_ALIAS_MACOS: NEWLINE_FORMAT_LINUX,
    NEWLINE_FORMAT_ALIAS_MSFT: NEWLINE_FORMAT_MICROSOFT,
    NEWLINE_FORMAT_ALIAS_UNIX: NEWLINE_FORMAT_LINUX,
    NEWLINE_FORMAT_ALIAS_WINDOWS: NEWLINE_FORMAT_MICROSOFT,
}

ALL_NEWLINE_FORMATS = sorted(NEWLINE_FORMATS + list(NEWLINE_FORMAT_ALIASES.keys()))

NEWLINE_VALUES = {
    NEWLINE_FORMAT_LINUX: "\n",
    NEWLINE_FORMAT_MICROSOFT: "\r\n",
    NEWLINE_FORMAT_NATIVE: None,
}

DEFAULT_NEWLINES = NEWLINE_FORMAT_NATIVE
DEFAULT_HEADING_TEXT = "Contents"
DEFAULT_HEADING_LEVEL = 1
DEFAULT_ADD_TRAILING_HEADING_CHARS = False
DEFAULT_ALT_LIST_CHAR = False
DEFAULT_NUMBERED = False
DEFAULT_SKIP_LEVEL = 0
DEFAULT_MAX_LEVEL = 0


####################


def _generate_comment(prog, argv, suffix="", with_full_command=False, with_datestamp=False):
    if with_full_command:
        command = "'" + " ".join(argv) + "'"
    else:
        command = os.path.basename(prog)
    datestamp = "".join([datetime.datetime.utcnow().isoformat(), "Z"])
    if with_datestamp:
        template = "Generated by {command} on {datestamp}{suffix}"
    else:
        template = "Generated by {command}{suffix}"
    comment_text = template.format(command=command, datestamp=datestamp, suffix=suffix)
    return comment_text


def _compute_diff(filename, input_text, output_text, context_lines=DIFF_CONTEXT_LINES):
    input_filename = os.path.join("a", filename)
    output_filename = os.path.join("b", filename)

    input_lines = input_text.split("\n")
    output_lines = output_text.split("\n")

    return difflib.unified_diff(
        input_lines,
        output_lines,
        fromfile=input_filename,
        tofile=output_filename,
        n=context_lines,
        # TODO: Remove this if we start using readlines() to get input/output text.
        lineterm="",
    )


def _add_file_arguments(parser):
    parser.add_argument(
        "input_filenames",
        nargs="*",
        action="store",
        default=[],
        metavar="INPUTFILE",
        help="input file[s], or '-' for stdin (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        action="store",
        dest="output_filename",
        default=None,
        metavar="OUTPUTFILE",
        help="output file, or '-' for stdout (default: stdout); conflicts with '--inplace'",
    )
    parser.add_argument(
        "-I",
        "--inplace",
        "--in-place",
        action="store_true",
        help="write changes to input file in place",
    )


def _add_diff_arguments(parser):
    diff_mutex_group = parser.add_mutually_exclusive_group()
    diff_mutex_group.add_argument(
        "-C",
        "--changed",
        "--show-changed",
        dest="show_changed",
        action="store_true",
        default=False,
        help="when used with '--inplace', note when a file has changed",
    )
    diff_mutex_group.add_argument(
        "-D",
        "--diff",
        "--show-diff",
        dest="show_diff",
        action="store_true",
        default=False,
        help="when used with '--inplace', show differences when a file has changed",
    )


def _add_newline_arguments(parser):
    newlines_mutex_group = parser.add_mutually_exclusive_group()
    newlines_mutex_group.add_argument(
        "--newlines",
        dest="newlines",
        action="store",
        choices=ALL_NEWLINE_FORMATS,
        default=DEFAULT_NEWLINES,
        help="newline format (default: {})".format(DEFAULT_NEWLINES),
    )
    newlines_mutex_group.add_argument(
        "-L",
        "--linux",
        dest="newlines",
        action="store_const",
        const=NEWLINE_FORMAT_LINUX,
        help="same as '--newlines {}'".format(NEWLINE_FORMAT_LINUX),
    )
    newlines_mutex_group.add_argument(
        "-M",
        "--microsoft",
        dest="newlines",
        action="store_const",
        const=NEWLINE_FORMAT_MICROSOFT,
        help="same as '--newlines {}'".format(NEWLINE_FORMAT_MICROSOFT),
    )
    newlines_mutex_group.add_argument(
        "-N",
        "--native",
        dest="newlines",
        action="store_const",
        const=NEWLINE_FORMAT_NATIVE,
        help="same as '--newlines {}'".format(NEWLINE_FORMAT_NATIVE),
    )


def _add_heading_arguments(parser):
    parser.add_argument(
        "-T",
        "--heading-text",
        action="store",
        default=DEFAULT_HEADING_TEXT,
        help="Text of heading above table of contents (default: '{default}')".format(default=DEFAULT_HEADING_TEXT),
    )
    parser.add_argument(
        "-H",
        "--heading-level",
        action="store",
        type=int,
        default=DEFAULT_HEADING_LEVEL,
        help="Level of heading above table of contents (default: {default})".format(default=DEFAULT_HEADING_LEVEL),
    )
    parser.add_argument(
        "-S",
        "--skip-level",
        action="store",
        type=int,
        default=DEFAULT_SKIP_LEVEL,
        help="Number of heading levels to leave out of table contents (default: {default})".format(
            default=DEFAULT_SKIP_LEVEL
        ),
    )
    parser.add_argument(
        "-X",
        "--max-level",
        action="store",
        type=int,
        default=DEFAULT_MAX_LEVEL,
        help="Maximum number of heading levels to include in table contents (default: {default})".format(
            default=DEFAULT_MAX_LEVEL
        ),
    )


def _add_option_arguments(parser):
    parser.add_argument(
        "-#",
        "--add-trailing-heading-chars",
        dest="add_trailing_heading_chars",
        action="store_true",
        default=DEFAULT_ADD_TRAILING_HEADING_CHARS,
        help="Add trailing '#' characters to the table of contents heading (default: {default})".format(
            default=DEFAULT_ADD_TRAILING_HEADING_CHARS
        ),
    )
    parser.add_argument(
        "-l",
        "--alt-list-char",
        "--alternate-list-character",
        action="store_true",
        default=DEFAULT_ALT_LIST_CHAR,
        help="Use alternate list character ('*') for table of contents entries (default: use '-')",
    )
    parser.add_argument(
        "-n",
        "--numbered",
        action="store_true",
        default=DEFAULT_NUMBERED,
        help="Add numbering to table of contents entries (default: {default})".format(default=DEFAULT_NUMBERED),
    )


def _add_comment_arguments(parser):
    comment_arg_group = parser.add_mutually_exclusive_group()
    comment_arg_group.add_argument(
        "-c",
        "--comment",
        action="store",
        default=None,
        help="Comment to add to Markdown source near table of contents (default: auto-generated)",
    )
    comment_arg_group.add_argument(
        "--no-comment",
        "--nocomment",
        dest="comment",
        action="store_const",
        const="",
        help="Do not add any comment to Markdown source",
    )
    return comment_arg_group


def _add_pre_commit_arguments(parser):
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help="Shortcut for '--inplace --changed' with static default comment",
    )


def _add_completion_arguments(parser):
    parser.add_argument(
        "--completion-help",
        action="store_true",
        help="Print instructions for enabling shell command-line autocompletion",
    )
    parser.add_argument(
        "--bash-completion",
        action="store_true",
        help="Print autocompletion code for Bash-compatible shells to evaluate",
    )


def _setup_args(argv):
    (prog, argv) = argparsing.grok_argv(argv)
    parser = argparsing.setup_argparse(
        prog=prog,
        description="Add or update a table of contents in one or more GitHub-flavored Markdown documents.",
    )

    _add_file_arguments(parser)
    _add_diff_arguments(parser)
    _add_newline_arguments(parser)
    _add_heading_arguments(parser)
    _add_option_arguments(parser)
    _add_comment_arguments(parser)
    _add_pre_commit_arguments(parser)
    _add_completion_arguments(parser)
    parser.add_argument("-V", "--version", action="version", version=get_version(prog))

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    return (prog, args)


def _check_newlines(cli_args):
    if cli_args.newlines not in NEWLINE_FORMATS:
        cli_args.newlines = NEWLINE_FORMAT_ALIASES[cli_args.newlines]


def _normalize_path(path):
    """Fully regularize a given filesystem path."""
    if path != "-":
        path = os.path.normcase(os.path.normpath(os.path.realpath(path)))
    return path


def _check_input_and_output_filenames(cli_args):
    """Check args found by `argparse.ArgumentParser`:py:class: and regularize."""
    if len(cli_args.input_filenames) == 0:
        cli_args.input_filenames.append("-")  # default to stdin

    if not cli_args.inplace:
        if cli_args.output_filename is None:
            cli_args.output_filename = "-"  # default to stdout
        if len(cli_args.input_filenames) > 1:
            raise RuntimeError("to process more than one input file at a time, use '--inplace'")
        output_filename = _normalize_path(cli_args.output_filename)
        input_filename = _normalize_path(cli_args.input_filenames[0])
        if input_filename != "-" and input_filename == output_filename:
            raise RuntimeError("input file and output file are the same; " "use '--inplace' to modify files in place")
    else:
        if cli_args.output_filename is not None:
            raise RuntimeError("output files do not make sense with '--inplace'")

        for i in range(len(cli_args.input_filenames)):
            if cli_args.input_filenames[i] == "-":
                raise RuntimeError("reading from stdin does not make sense with '--inplace'")


def _check_completion_args(cli_args):
    return any([cli_args.completion_help, cli_args.bash_completion])


def _do_completion(cli_args, prog):
    if cli_args.completion_help:
        print(completion.get_instructions(prog, ["--bash-completion"]))
    elif cli_args.bash_completion:
        print(completion.get_commands(prog))


def _check_pre_commit_args(cli_args):
    if not cli_args.pre_commit:
        return
    cli_args.inplace = True
    if not cli_args.show_diff:
        cli_args.show_changed = True


def _check_diff_args(cli_args):
    if cli_args.show_changed and not cli_args.inplace:
        raise RuntimeError("'-C/--show-changed' only makes sense with '--inplace'")
    if cli_args.show_diff and not cli_args.inplace:
        raise RuntimeError("'-D/--show-diff' only makes sense with '--inplace'")


def _set_default_comment(cli_args, prog, argv):
    if cli_args.comment is not None:
        return
    cli_args.comment = (
        _generate_comment(prog, argv, suffix=" pre-commit hook")
        if cli_args.pre_commit
        else _generate_comment(prog, argv, with_full_command=True, with_datestamp=True)
    )


def main(*argv):
    """Do the thing."""
    (prog, args) = _setup_args(argv)

    if _check_completion_args(args):
        _do_completion(args, prog)
        return STATUS_SUCCESS

    _check_pre_commit_args(args)
    _check_diff_args(args)
    _check_newlines(args)
    _check_input_and_output_filenames(args)
    _set_default_comment(args, prog, argv)

    overall_status = STATUS_SUCCESS

    for input_filename in args.input_filenames:
        file_status = STATUS_SUCCESS
        input_iofile = iofile.TextIOFile(
            input_filename,
            input_newline="",
            output_newline=NEWLINE_VALUES[args.newlines],
        )
        output_iofile = (
            input_iofile
            if args.inplace
            else iofile.TextIOFile(
                args.output_filename,
                input_newline="",
                output_newline=NEWLINE_VALUES[args.newlines],
            )
        )

        input_iofile.open_for_input()
        md = mdfile.MarkdownFile(infile=input_iofile.file, infilename=input_iofile.printable_name)

        try:
            input_text = md.read()
            md.parse(
                heading_text=args.heading_text,
                heading_level=args.heading_level,
                skip_level=args.skip_level,
                max_level=args.max_level,
            )
        except (TypeError, ValueError) as e:
            if not args.inplace:
                raise SystemExit(e)
            overall_status = STATUS_FAILURE
            file_status = STATUS_FAILURE
            print(e, file=sys.stderr)

        input_iofile.close()

        if file_status != STATUS_FAILURE:
            output_iofile.open_for_output()

            md.write(
                numbered=args.numbered,
                toc_comment=args.comment,
                alt_list_char=args.alt_list_char,
                add_trailing_heading_chars=args.add_trailing_heading_chars,
                outfile=output_iofile.file,
            )

            output_iofile.close()

            if args.inplace and (args.show_changed or args.show_diff):
                output_iofile.open_for_input()
                output_text = output_iofile.file.read()
                if input_text != output_text:
                    file_status = STATUS_CHANGED
                    if overall_status != STATUS_FAILURE:
                        overall_status = file_status
                    print(
                        "Updated {}".format(output_iofile.file.name),
                        file=sys.stderr,
                    )
                    if args.show_diff:
                        for line in _compute_diff(output_iofile.file.name, input_text, output_text):
                            print(line)
                output_iofile.close()

    return overall_status


if __name__ == "__main__":
    sys.exit(main())
