from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from driftkb.core.models import ValidationStatus

subprocess_run = subprocess.run

EXPECTED_RE = re.compile(r"^\s*#\s*expected:\s*match_count\s*>=\s*(?P<count>\d+)\s*$")
FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$")
SAMPLE_LINES = 20
SAMPLE_CHARS = 4000
_DANGEROUS_RG_FLAGS = {
    "-L",
    "--config",
    "--follow",
    "--pre",
    "--pre-glob",
}
_DANGEROUS_RG_PREFIXES = (
    "--config=",
    "--pre=",
    "--pre-glob=",
)
_RG_OPTIONS_WITH_VALUE = {
    "-A",
    "-B",
    "-C",
    "-e",
    "-f",
    "-g",
    "-j",
    "-m",
    "-r",
    "-t",
    "-T",
    "--after-context",
    "--before-context",
    "--context",
    "--colors",
    "--encoding",
    "--engine",
    "--file",
    "--glob",
    "--iglob",
    "--ignore-file",
    "--max-count",
    "--max-depth",
    "--path-separator",
    "--regexp",
    "--replace",
    "--sort",
    "--threads",
    "--type",
    "--type-add",
    "--type-clear",
}
_RG_PATTERN_OPTIONS = {"-e", "--regexp"}
_RG_PATH_VALUE_OPTIONS = {"-f", "--file", "--ignore-file"}
_RG_PATH_ONLY_FLAGS = {"--files"}


@dataclass(frozen=True)
class ExpectedMatchCount:
    minimum: int
    raw: str


@dataclass(frozen=True)
class VerifyBlock:
    language: str
    body: str
    block_index: int


@dataclass(frozen=True)
class VerifyBlockResult:
    block_index: int
    command: str | None
    expected: str | None
    actual_match_count: int | None
    result: ValidationStatus
    message: str
    stdout_sample: str = ""
    stderr_sample: str = ""


def extract_verify_blocks(markdown_body: str) -> tuple[VerifyBlock, ...]:
    blocks: list[VerifyBlock] = []
    lines = markdown_body.splitlines()
    index = 0
    block_index = 0

    while index < len(lines):
        match = FENCE_RE.match(lines[index])
        if not match:
            index += 1
            continue

        fence = match.group("fence")
        info = match.group("info").strip()
        body_lines: list[str] = []
        index += 1

        while index < len(lines):
            line = lines[index]
            if line.startswith(fence[0] * len(fence)):
                break
            body_lines.append(line)
            index += 1

        if _info_contains_verify(info):
            blocks.append(
                VerifyBlock(
                    language=info,
                    body="\n".join(body_lines),
                    block_index=block_index,
                )
            )
            block_index += 1

        index += 1

    return tuple(blocks)


def parse_expected(line: str) -> ExpectedMatchCount | None:
    match = EXPECTED_RE.match(line)
    if not match:
        return None
    return ExpectedMatchCount(minimum=int(match.group("count")), raw=line.strip())


def run_verify_block(
    block: VerifyBlock,
    source_root: Path,
    allow_shell: bool = False,
    timeout_seconds: float = 10,
    capture_samples: bool = False,
) -> VerifyBlockResult:
    command = _extract_command(block.body)
    expected = _extract_expected(block.body)

    if command is None:
        return VerifyBlockResult(
            block_index=block.block_index,
            command=None,
            expected=expected.raw if expected else None,
            actual_match_count=None,
            result=ValidationStatus.WARN,
            message="verify block has no command",
        )

    if expected is None:
        return VerifyBlockResult(
            block_index=block.block_index,
            command=command,
            expected=None,
            actual_match_count=None,
            result=ValidationStatus.WARN,
            message="verify block has no expected assertion",
        )

    if not _is_rg_command(command):
        message = "only rg verify commands are supported"
        if allow_shell:
            message = "shell verify execution is not implemented; only rg commands are supported"
        return VerifyBlockResult(
            block_index=block.block_index,
            command=command,
            expected=expected.raw if expected else None,
            actual_match_count=None,
            result=ValidationStatus.WARN,
            message=message,
        )

    try:
        args = _split_command(command)
    except ValueError as exc:
        return VerifyBlockResult(
            block_index=block.block_index,
            command=command,
            expected=expected.raw if expected else None,
            actual_match_count=None,
            result=ValidationStatus.WARN,
            message=f"could not parse rg command: {exc}",
        )

    validation_error = _validate_rg_args(args, source_root)
    if validation_error is not None:
        return VerifyBlockResult(
            block_index=block.block_index,
            command=command,
            expected=expected.raw,
            actual_match_count=None,
            result=ValidationStatus.WARN,
            message=validation_error,
        )

    try:
        completed = subprocess_run(
            _args_with_no_config(args),
            cwd=source_root,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return VerifyBlockResult(
            block_index=block.block_index,
            command=command,
            expected=expected.raw if expected else None,
            actual_match_count=None,
            result=ValidationStatus.WARN,
            message="rg is not installed or not available on PATH",
        )
    except OSError as exc:
        return VerifyBlockResult(
            block_index=block.block_index,
            command=command,
            expected=expected.raw if expected else None,
            actual_match_count=None,
            result=ValidationStatus.WARN,
            message=f"could not run rg verify command: {exc}",
        )
    except subprocess.TimeoutExpired as exc:
        return VerifyBlockResult(
            block_index=block.block_index,
            command=command,
            expected=expected.raw if expected else None,
            actual_match_count=None,
            result=ValidationStatus.WARN,
            message=f"rg verify command timed out after {timeout_seconds:g} seconds",
            stdout_sample=_sample(exc.stdout or "", capture=capture_samples),
            stderr_sample=_sample(exc.stderr or "", capture=capture_samples),
        )

    stdout_sample = _sample(completed.stdout, capture=capture_samples)
    stderr_sample = _sample(completed.stderr, capture=capture_samples)

    if completed.returncode == 0:
        match_count = _non_empty_line_count(completed.stdout)
    elif completed.returncode == 1:
        match_count = 0
    else:
        return VerifyBlockResult(
            block_index=block.block_index,
            command=command,
            expected=expected.raw if expected else None,
            actual_match_count=None,
            result=ValidationStatus.WARN,
            message=f"rg exited with code {completed.returncode}",
            stdout_sample=stdout_sample,
            stderr_sample=stderr_sample,
        )

    if expected is not None and match_count < expected.minimum:
        return VerifyBlockResult(
            block_index=block.block_index,
            command=command,
            expected=expected.raw,
            actual_match_count=match_count,
            result=ValidationStatus.FAIL,
            message=f"expected match_count >= {expected.minimum}, got {match_count}",
            stdout_sample=stdout_sample,
            stderr_sample=stderr_sample,
        )

    return VerifyBlockResult(
        block_index=block.block_index,
        command=command,
        expected=expected.raw if expected else None,
        actual_match_count=match_count,
        result=ValidationStatus.PASS,
        message="verify block passed",
        stdout_sample=stdout_sample,
        stderr_sample=stderr_sample,
    )


def _info_contains_verify(info: str) -> bool:
    return any(part == "verify" or "verify" in part.split("-") for part in info.split())


def _extract_command(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped
    return None


def _extract_expected(body: str) -> ExpectedMatchCount | None:
    for line in body.splitlines():
        expected = parse_expected(line)
        if expected is not None:
            return expected
    return None


def _is_rg_command(command: str) -> bool:
    try:
        args = _split_command(command)
    except ValueError:
        return False
    return bool(args) and args[0] == "rg"


def _validate_rg_args(args: list[str], source_root: Path) -> str | None:
    if any(_is_dangerous_rg_arg(arg) for arg in args[1:]):
        return "rg verify command uses an unsafe option"

    source_root = source_root.resolve()
    for option_value in _extract_rg_path_option_values(args):
        if _has_absolute_or_parent_path(option_value):
            return "rg verify command option paths must be relative to source root"
    for operand in _extract_rg_path_operands(args):
        error = _validate_relative_operand(operand, source_root)
        if error is not None:
            return error
    if not _extract_rg_path_operands(args):
        return "rg verify command must include an explicit path operand relative to source root"
    return None


def _split_command(command: str) -> list[str]:
    args: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0

    while index < len(command):
        char = command[index]
        if quote is None:
            if char.isspace():
                if current:
                    args.append("".join(current))
                    current = []
                index += 1
                continue
            if char in {"'", '"'}:
                quote = char
                index += 1
                continue
            current.append(char)
            index += 1
            continue

        if char == quote:
            quote = None
            index += 1
            continue
        if quote == '"' and char == "\\" and index + 1 < len(command) and command[index + 1] in {'"', "\\"}:
            current.append(command[index + 1])
            index += 2
            continue
        current.append(char)
        index += 1

    if quote is not None:
        raise ValueError("No closing quotation")
    if current:
        args.append("".join(current))
    return args


def _extract_rg_path_operands(args: list[str]) -> tuple[str, ...]:
    operands: list[str] = []
    pattern_seen = _has_path_only_flag(args)
    end_options = False
    skip_next: str | None = None

    for arg in args[1:]:
        if skip_next is not None:
            if skip_next == "pattern":
                pattern_seen = True
            skip_next = None
            continue

        if not end_options and arg == "--":
            end_options = True
            continue

        if not end_options:
            option = _option_with_value(arg)
            if option is not None:
                if not _option_value_is_inline(arg, option):
                    skip_next = "pattern" if option in _RG_PATTERN_OPTIONS else "value"
                elif option in _RG_PATTERN_OPTIONS:
                    pattern_seen = True
                continue
            if arg.startswith("-"):
                continue

        if not pattern_seen:
            pattern_seen = True
            continue
        operands.append(arg)

    return tuple(operands)


def _has_path_only_flag(args: list[str]) -> bool:
    return any(arg in _RG_PATH_ONLY_FLAGS for arg in args[1:])


def _extract_rg_path_option_values(args: list[str]) -> tuple[str, ...]:
    values: list[str] = []
    skip_next_for: str | None = None
    for arg in args[1:]:
        if skip_next_for is not None:
            if skip_next_for in _RG_PATH_VALUE_OPTIONS:
                values.append(arg)
            skip_next_for = None
            continue
        if arg == "--":
            break
        option = _option_with_value(arg)
        if option is None:
            continue
        if _option_value_is_inline(arg, option):
            if option in _RG_PATH_VALUE_OPTIONS:
                values.append(_inline_option_value(arg, option))
        else:
            skip_next_for = option
    return tuple(values)


def _option_with_value(arg: str) -> str | None:
    if arg in _RG_OPTIONS_WITH_VALUE:
        return arg
    for option in _RG_OPTIONS_WITH_VALUE:
        if option.startswith("--") and arg.startswith(f"{option}="):
            return option
    for option in _RG_OPTIONS_WITH_VALUE:
        if option.startswith("-") and not option.startswith("--") and arg.startswith(option) and len(arg) > len(option):
            return option
    return None


def _option_value_is_inline(arg: str, option: str) -> bool:
    return arg != option


def _inline_option_value(arg: str, option: str) -> str:
    if option.startswith("--"):
        return arg.split("=", 1)[1]
    return arg[len(option) :]


def _validate_relative_operand(operand: str, source_root: Path) -> str | None:
    if operand == "-":
        return "rg verify command cannot read from stdin"
    if _has_absolute_or_parent_path(operand):
        return "rg verify command paths must be relative to source root"
    resolved = (source_root / operand).resolve()
    try:
        resolved.relative_to(source_root)
    except ValueError:
        return "rg verify command paths must stay inside source root"
    return None


def _has_absolute_or_parent_path(value: str) -> bool:
    if not value:
        return False
    if value.startswith(("~", "file:")):
        return True
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute():
        return True
    parts = re.split(r"[\\/]+", value)
    return ".." in parts


def _is_dangerous_rg_arg(arg: str) -> bool:
    return arg in _DANGEROUS_RG_FLAGS or any(arg.startswith(prefix) for prefix in _DANGEROUS_RG_PREFIXES)


def _args_with_no_config(args: list[str]) -> list[str]:
    if "--no-config" in args:
        return args
    return [args[0], "--no-config", *args[1:]]


def _non_empty_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _sample(text: str, *, capture: bool = False) -> str:
    line_count = len(text.splitlines()[:SAMPLE_LINES])
    if not line_count:
        return ""
    if not capture:
        return f"<redacted {line_count} line(s)>"
    sample = "\n".join(text.splitlines()[:SAMPLE_LINES])
    return sample[:SAMPLE_CHARS]
