"""Validate package transport configuration before it can be exposed."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass
class ConfigAuditResult:
    """Machine-readable configuration security result."""

    ok: bool
    transport: str
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "ok": self.ok,
            "transport": self.transport,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _error(errors: list[dict[str, str]], code: str, message: str) -> None:
    errors.append({"code": code, "message": message})


def _strip_inline_comment(value: str) -> str:
    """Remove a YAML comment without touching ``#`` inside quoted values.

    The fallback parser intentionally handles only the small configuration
    subset needed by ``doctor``. It still needs to accept the repository's
    checked-in example, which uses inline comments after scalar values.
    """

    quote: str | None = None
    escaped = False
    for index, character in enumerate(value):
        if quote is not None:
            if character == "\\" and quote == '"' and not escaped:
                escaped = True
                continue
            if character == quote and not escaped:
                quote = None
            escaped = False
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].strip()
    return value.strip()


def _parse_scalar(value: str) -> Any:
    stripped = _strip_inline_comment(value)
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        stripped = stripped[1:-1]
    if stripped.casefold() in {"true", "yes", "on"}:
        return True
    if stripped.casefold() in {"false", "no", "off"}:
        return False
    if stripped.casefold() in {"null", "none", "~"}:
        return None
    return stripped


def _minimal_yaml_config(text: str) -> dict[str, Any]:
    """Read the small server subset when optional PyYAML is not installed."""

    result: dict[str, Any] = {"server": {}}
    section: str | None = None
    subsection: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        indent = len(line) - len(line.lstrip())
        key, raw_value = line.strip().split(":", 1)
        key = key.strip()
        if indent == 0:
            section = key
            subsection = None
            result.setdefault(section, {})
        elif section == "server" and indent == 2:
            if raw_value.strip():
                result["server"][key] = _parse_scalar(raw_value)
                subsection = None
            else:
                subsection = key
                result["server"][key] = {}
        elif section == "server" and indent >= 4 and subsection:
            result["server"].setdefault(subsection, {})[key] = _parse_scalar(raw_value)
    return result


def load_config(path: Path | str) -> dict[str, Any]:
    """Load YAML without making PyYAML a hard dependency of the operator."""

    config_path = Path(path).expanduser().resolve()
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return _minimal_yaml_config(text)
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise ValueError("configuration root must be a mapping")
    return dict(loaded)


def audit_config(config: Mapping[str, Any]) -> ConfigAuditResult:
    """Enforce the repository's safe defaults for network transports.

    stdio is a local child-process protocol and does not carry HTTP
    credentials. HTTP/SSE transports are considered deployable only when the
    vendor server's bearer middleware, rate limit, metrics and JSON logging
    are all explicitly enabled.
    """

    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    raw_server = config.get("server")
    if "server" in config and not isinstance(raw_server, Mapping):
        _error(errors, "invalid_server", "server configuration must be a mapping")
    server = _mapping(raw_server)
    transport = str(server.get("transport") or "stdio").strip().casefold()
    if transport not in {"stdio", "sse", "streamable-http"}:
        _error(errors, "unsupported_transport", f"unsupported server transport: {transport!r}")
    if transport in {"sse", "streamable-http"}:
        auth = _mapping(server.get("auth"))
        token = str(auth.get("bearer_token") or "").strip()
        placeholder = token.startswith("<") or token.startswith("${") or "REPLACE" in token.upper()
        if len(token) < 16 or placeholder:
            _error(errors, "network_auth_required", "HTTP/SSE transport requires a non-placeholder bearer token")
        rate_limit = _mapping(server.get("rate_limit"))
        if rate_limit.get("enabled") is not True:
            _error(errors, "network_rate_limit_required", "HTTP/SSE transport requires server.rate_limit.enabled=true")
        metrics = _mapping(server.get("metrics"))
        if metrics.get("enabled") is not True:
            _error(errors, "network_metrics_required", "HTTP/SSE transport requires server.metrics.enabled=true")
        logging = _mapping(server.get("logging"))
        if str(logging.get("format") or "").casefold() != "json":
            _error(errors, "network_json_logging_required", "HTTP/SSE transport requires server.logging.format=json")
        host = str(server.get("host") or "127.0.0.1")
        if host in {"0.0.0.0", "::"}:
            warnings.append(
                {
                    "code": "public_bind",
                    "message": "server binds on every interface; keep bearer auth and firewall rules enabled",
                }
            )
    return ConfigAuditResult(not errors, transport, errors, warnings)


def audit_config_file(path: Path | str) -> ConfigAuditResult:
    """Load and audit one config file without including its token in output."""

    return audit_config(load_config(path))
