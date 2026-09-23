"""Prepare the pinned, loopback-only RAGFlow development Compose stack.

The default mode is read-only and prints a deterministic plan.  ``--apply``
clones the exact upstream commit into an operator-selected workspace and starts
only the CPU RAGFlow service through the upstream Compose definition plus the
Farol loopback/pinned-image override.  Nothing runs during imports, planning or
core tests.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = PROJECT_ROOT / "config" / "ragflow" / "dev-lock.json"
OVERRIDE_PATH = PROJECT_ROOT / "config" / "ragflow" / "compose.dev.override.yaml"
IMAGE_DIGEST_PATTERN = re.compile(r"^[^\s@]+@sha256:[0-9a-fA-F]{64}$")


class RagFlowDevError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _read_lock(path: Path = LOCK_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RagFlowDevError("lock_invalid", "RAGFlow development lock is unavailable or invalid") from exc
    required = {
        "repository",
        "tag",
        "commit",
        "compose_file",
        "profiles",
        "services",
        "tei_image_digest",
        "embedding_model",
        "sdk_version",
    }
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or not required.issubset(payload)
        or not re.fullmatch(r"[0-9a-f]{40}", str(payload.get("commit") or ""))
        or str(payload.get("sdk_version")) != "0.27.2"
        or not isinstance(payload.get("profiles"), list)
        or not payload["profiles"]
        or any(not isinstance(profile, str) or not profile for profile in payload["profiles"])
        or not isinstance(payload.get("services"), list)
        or not payload["services"]
        or any(not isinstance(service, str) or not service for service in payload["services"])
        or not IMAGE_DIGEST_PATTERN.fullmatch(str(payload.get("tei_image_digest") or ""))
        or not isinstance(payload.get("embedding_model"), str)
        or not payload["embedding_model"]
    ):
        raise RagFlowDevError("lock_invalid", "RAGFlow development lock does not pin the required inputs")
    return payload


def build_plan(
    workspace: Path,
    image_digest: str | None,
    *,
    lock_path: Path = LOCK_PATH,
    override_path: Path = OVERRIDE_PATH,
) -> dict[str, Any]:
    lock = _read_lock(lock_path)
    resolved_workspace = workspace.expanduser().resolve()
    digest = str(image_digest or "").strip()
    blockers: list[str] = []
    if not IMAGE_DIGEST_PATTERN.fullmatch(digest):
        blockers.append("DOCOPS_RAGFLOW_IMAGE_DIGEST")
    upstream_compose = resolved_workspace / str(lock["compose_file"])
    compose_command = [
        "docker",
        "compose",
        "-f",
        str(upstream_compose),
        "-f",
        str(override_path.resolve()),
    ]
    for profile in lock["profiles"]:
        compose_command.extend(["--profile", str(profile)])
    compose_command.extend(["up", "-d", *[str(service) for service in lock["services"]]])
    return {
        "schema_version": 1,
        "kind": "ragflow_dev_plan",
        "ok": not blockers,
        "status": "ready" if not blockers else "blocked",
        "blockers": blockers,
        "workspace": str(resolved_workspace),
        "source": {
            "repository": lock["repository"],
            "tag": lock["tag"],
            "commit": lock["commit"],
        },
        "runtime": {
            "image_digest_configured": not blockers,
            "sdk_version": lock["sdk_version"],
            "profiles": list(lock["profiles"]),
            "services": list(lock["services"]),
            "tei_image_digest": lock["tei_image_digest"],
            "embedding_model": lock["embedding_model"],
            "endpoint": "http://127.0.0.1:${DOCOPS_RAGFLOW_API_PORT:-9380}",
            "network_exposure": "loopback-only",
        },
        "commands": {
            "clone": [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                str(lock["repository"]),
                str(resolved_workspace),
            ],
            "fetch": ["git", "-C", str(resolved_workspace), "fetch", "--depth", "1", "origin", str(lock["commit"])],
            "checkout": ["git", "-C", str(resolved_workspace), "checkout", "--detach", str(lock["commit"])],
            "compose": compose_command,
        },
    }


def _run(command: list[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, env=dict(env) if env is not None else None, check=False)
    if completed.returncode != 0:
        raise RagFlowDevError("command_failed", f"command failed with exit code {completed.returncode}: {command[0]}")


def apply_plan(plan: Mapping[str, Any], image_digest: str) -> None:
    if plan.get("ok") is not True:
        raise RagFlowDevError("missing_external_inputs", "a pinned RAGFlow image digest is required")
    workspace = Path(str(plan["workspace"]))
    commands = plan.get("commands")
    if not isinstance(commands, Mapping):
        raise RagFlowDevError("plan_invalid", "RAGFlow development plan has no commands")
    if workspace.exists():
        if not (workspace / ".git").is_dir():
            raise RagFlowDevError("workspace_not_empty", "existing RAGFlow workspace is not the pinned checkout")
        origin = subprocess.run(
            ["git", "-C", str(workspace), "remote", "get-url", "origin"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        expected_repository = str(plan["source"]["repository"]).rstrip("/")
        if origin.returncode != 0 or origin.stdout.strip().rstrip("/") != expected_repository:
            raise RagFlowDevError(
                "workspace_source_mismatch",
                "existing RAGFlow workspace does not use the pinned upstream repository",
            )
    else:
        workspace.parent.mkdir(parents=True, exist_ok=True)
        _run([str(item) for item in commands["clone"]])
    _run([str(item) for item in commands["fetch"]])
    _run([str(item) for item in commands["checkout"]])
    head = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    expected = str(plan["source"]["commit"])
    if head.returncode != 0 or head.stdout.strip() != expected:
        raise RagFlowDevError("source_mismatch", "RAGFlow checkout does not match the pinned commit")
    environment = dict(os.environ)
    environment["DOCOPS_RAGFLOW_IMAGE_DIGEST"] = image_digest
    environment["RAGFLOW_IMAGE"] = image_digest
    environment["DOCOPS_RAGFLOW_TEI_IMAGE_DIGEST"] = str(plan["runtime"]["tei_image_digest"])
    environment["TEI_IMAGE_CPU"] = str(plan["runtime"]["tei_image_digest"])
    environment["TEI_MODEL"] = str(plan["runtime"]["embedding_model"])
    environment["COMPOSE_PROFILES"] = ",".join(str(item) for item in plan["runtime"]["profiles"])
    _run([str(item) for item in commands["compose"]], cwd=workspace / "docker", env=environment)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--image-digest", default=os.environ.get("DOCOPS_RAGFLOW_IMAGE_DIGEST"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(args.workspace, args.image_digest)
        if args.apply:
            apply_plan(plan, str(args.image_digest or ""))
            plan = {**plan, "status": "started", "applied": True}
        else:
            plan = {**plan, "applied": False}
        print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
        return 0 if plan["ok"] else 2
    except RagFlowDevError as exc:
        payload = {"schema_version": 1, "ok": False, "status": "blocked", "reason": exc.code, "message": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
