"""Pure block/allow decisions for the Claude Code Bash hook.

These functions receive only already-collected metadata. They never read files, run Git, invoke a
quality gate, or interact with live trading, which keeps every policy decision deterministic and
unit-testable.

The hook guards the boundaries that must hold regardless of which agent is driving and regardless
of process state: live trading is never touched, a credential never reaches a commit, a code change
never lands directly on ``main``, and a gate is never weakened to make a branch pass. Process
sequencing is not enforced here -- the board and the orchestrator own that.
"""

from __future__ import annotations

import io
import re
import tokenize
from dataclasses import dataclass

_BOUNDARY = re.compile(r"\bgit\s+(?:commit|push)\b", re.IGNORECASE)
_COMMIT = re.compile(r"\bgit\s+commit\b", re.IGNORECASE)
_PUSH = re.compile(r"\bgit\s+push\b", re.IGNORECASE)
_LIVE_COMMAND = re.compile(
    r"(?:\b(?:uv\s+run\s+)?python(?:\.exe)?\s+-m\s+"
    r"live\.(?:run|preflight|parity_check)\b|\bjust\s+live(?:-[\w]+)*(?:-execute)?\b)",
    re.IGNORECASE,
)
_RUNNER_CONTROL = re.compile(
    r"\b(?:systemctl|service|sc(?:\.exe)?|net)\s+(?:start|stop|restart)\b"
    r".*\b(?:runner|trading[-_]system|qplus)\b",
    re.IGNORECASE,
)
_ORDER_ACTION = re.compile(
    r"(?:\bmt5(?:\.exe)?\s+(?:order|position|trade)\s+"
    r"(?:place|send|submit|modify|close|cancel)\b|"
    r"\b(?:mt5|mt5bridge|bridge)\b.*\."
    r"(?:order_send|place_order|modify_order|cancel_order|close_position)\b)",
    re.IGNORECASE,
)
_FORCE = re.compile(r"(?:^|\s)(?:-f|--force|--force-with-lease(?:=[^\s]+)?)(?:\s|$)", re.IGNORECASE)
_MAIN_REF = re.compile(r"(?:^|[\s:/'\"])(?:refs/heads/)?main(?:$|[\s'\"])", re.IGNORECASE)
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_TOKEN = re.compile(r"\b(?:sk|gh[opusr]|github_pat)-[A-Za-z0-9_]{20,}\b")
_AWS_KEY = re.compile(r"\bAKIA[A-Z0-9]{16}\b")
_NAMED_SECRET = re.compile(
    r"\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret)\b"
    r"\s*[:=]\s*['\"]?(?P<value>[^\s,'\"#]{8,})",
    re.IGNORECASE,
)
_PLACEHOLDERS = re.compile(
    r"^(?:placeholder|example|dummy|fake|test|changeme|change-me|redacted|none|null|"
    r"\$?\{[^}]+\}[\\nrt]*|<[^>]+>)$",
    re.IGNORECASE,
)
_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore\b(?P<suffix>.*)", re.IGNORECASE)
_NOQA = re.compile(r"#\s*noqa\b(?P<suffix>.*)", re.IGNORECASE)
_SKIP = re.compile(r"(?:@|\.)pytest\.mark\.skip(?:if)?\b", re.IGNORECASE)
_VERIFY_BYPASS = re.compile(r"(?:^|\s)--no-" + "verify(?:\\s|$)")


@dataclass(frozen=True)
class Decision:
    """One deterministic hook decision with a fixed, non-sensitive explanation."""

    allowed: bool
    reason: str = ""


def _allow() -> Decision:
    return Decision(True)


def _deny(reason: str) -> Decision:
    return Decision(False, reason)


def _added_lines(diff: str) -> tuple[str, ...]:
    return tuple(
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def _added_python_lines(diff: str) -> tuple[str, ...]:
    current_path: str | None = None
    lines: list[str] = []
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_path = raw.removeprefix("+++ b/")
            continue
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        if current_path is None or current_path.endswith(".py"):
            lines.append(raw[1:])
    return tuple(lines)


def _python_controls(line: str) -> tuple[str, str]:
    """Split one added line into its code and its comments, so a string literal cannot trip a
    suppression check and a comment cannot hide one."""

    try:
        tokens = tuple(tokenize.generate_tokens(io.StringIO(f"{line.lstrip()}\n").readline))
    except (IndentationError, tokenize.TokenError):
        return line, ""
    code = "".join(
        token.string for token in tokens if token.type not in {tokenize.COMMENT, tokenize.STRING}
    )
    comments = " ".join(token.string for token in tokens if token.type == tokenize.COMMENT)
    return code, comments


def _has_broad_ignore(comments: str) -> bool:
    """A suppression is broad when it names no specific rule, which silences future errors too."""

    type_ignore = _TYPE_IGNORE.search(comments)
    if type_ignore is not None:
        suffix = type_ignore.group("suffix").strip()
        if re.fullmatch(r"\[[A-Za-z0-9_, -]+\]", suffix) is None:
            return True
    noqa = _NOQA.search(comments)
    if noqa is None:
        return False
    suffix = noqa.group("suffix").strip()
    if not suffix.startswith(":"):
        return True
    codes = [code.strip().upper() for code in suffix.removeprefix(":").split(",")]
    return not codes or any(
        code == "ALL" or re.fullmatch(r"[A-Z]{1,4}\d{3}", code) is None for code in codes
    )


def _widens_per_file_ignores(diff: str) -> bool:
    in_section = False
    current_path: str | None = None
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_path = raw.removeprefix("+++ b/")
            in_section = False
            continue
        if raw.startswith(("diff ", "@@")):
            in_section = False
            continue
        if current_path is not None and not current_path.endswith(".toml"):
            continue
        content = raw[1:].strip() if raw[:1] in {"+", "-", " "} else raw.strip()
        if content.startswith("[") and content.endswith("]"):
            in_section = "per-file-ignores" in content.casefold()
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        if "per-file-ignores" in content.casefold() or in_section:
            return True
    return False


def dangerous_command_decision(command: str) -> Decision:
    """Block live execution, runner control, order actions, and forced pushes to main."""

    forced_main = bool(
        _PUSH.search(command) and _FORCE.search(command) and _MAIN_REF.search(command)
    )
    if (
        _LIVE_COMMAND.search(command)
        or _RUNNER_CONTROL.search(command)
        or _ORDER_ACTION.search(command)
    ):
        return _deny(
            "Blocked: live execution, runner control, and order operations are prohibited."
        )
    if forced_main:
        return _deny("Blocked: force-pushing main is prohibited.")
    return _allow()


def secret_decision(staged_diff: str) -> Decision:
    """Block likely credentials in added staged lines without returning matched content."""

    for line in _added_lines(staged_diff):
        if _PRIVATE_KEY.search(line) or _TOKEN.search(line) or _AWS_KEY.search(line):
            return _deny("Blocked: the staged diff contains a likely credential.")
        match = _NAMED_SECRET.search(line)
        if match is not None and _PLACEHOLDERS.fullmatch(match.group("value")) is None:
            return _deny("Blocked: the staged diff contains a likely credential.")
    return _allow()


def main_branch_decision(command: str, branch: str, risk_class: str) -> Decision:
    """Allow direct main commits and pushes only for changes classified as trivial R0."""

    if not (_COMMIT.search(command) or _PUSH.search(command)) or risk_class == "R0":
        return _allow()
    targets_main = branch.casefold() == "main" or bool(
        _PUSH.search(command) and _MAIN_REF.search(command)
    )
    if targets_main:
        return _deny("Blocked: R1-R3 changes must use a feature branch and pull request.")
    return _allow()


def bypass_decision(command: str, diff: str) -> Decision:
    """Block verification bypass flags and newly added broad suppressions or skips."""

    if _VERIFY_BYPASS.search(command):
        return _deny("Blocked: bypassing commit verification is prohibited.")
    if _BOUNDARY.search(command) is None:
        return _allow()
    for line in _added_python_lines(diff):
        code, comments = _python_controls(line)
        if _has_broad_ignore(comments) or _SKIP.search(code):
            return _deny("Blocked: newly added broad ignores or test skips require removal.")
    if _widens_per_file_ignores(diff):
        return _deny("Blocked: widening per-file ignores is prohibited.")
    return _allow()
