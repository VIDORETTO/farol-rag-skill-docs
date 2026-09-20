"""Build a wheel in isolation and smoke-test the provider-free package."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops import __version__  # noqa: E402

_REPRODUCIBLE_SOURCE_DATE_EPOCH = "315532800"


def command_failure_details(completed: subprocess.CompletedProcess[str]) -> str:
    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        return f"stdout={completed.stdout[-2000:]} stderr={completed.stderr[-2000:]}"
    if not isinstance(payload, dict):
        return f"stdout={completed.stdout[-2000:]} stderr={completed.stderr[-2000:]}"
    return json.dumps(
        {
            "errors": payload.get("errors", []),
            "outcome": payload.get("outcome"),
            "stderr_tail": completed.stderr[-2000:],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", action="store_true", help="accepted compatibility flag; core is always provider-free")
    parser.add_argument("--require-rag", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.require_rag:
        raise RuntimeError("the legacy wheel RAG gate was removed; run the external RAGFlow profile instead")

    root = PROJECT_ROOT
    with tempfile.TemporaryDirectory(prefix="docops-wheel-") as temporary:
        workspace = Path(temporary)
        wheel_dir = workspace / "wheel"
        target_dir = workspace / "installed"
        wheel_dir.mkdir()
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheel_dir), str(root)],
            check=True,
            cwd=root,
            env={**os.environ, "SOURCE_DATE_EPOCH": _REPRODUCIBLE_SOURCE_DATE_EPOCH},
        )
        wheels = sorted(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected exactly one wheel, found {len(wheels)}")
        wheel = wheels[0]
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            data_prefix = wheel.stem.rsplit("-", 3)[0]
            required = {
                "docops/__init__.py",
                "docops/backends/ragflow.py",
                "docops/rag_snapshots.py",
                "docops/extractors/registry.py",
                "docops/ir/core.py",
                "docops/templates/router.md",
                "docops/schemas/manifest.schema.json",
                "docops/schemas/evaluation.schema.json",
                f"{data_prefix}.data/data/share/docops/skills/docops-agent/SKILL.md",
                f"{data_prefix}.data/data/share/docops/skills/docops-agent/agents/openai.yaml",
            }
            missing = sorted(required - names)
            if missing:
                raise RuntimeError(f"wheel is missing package files: {missing}")
            metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
            metadata = archive.read(metadata_name).decode("utf-8")
            if f"Version: {__version__}" not in metadata:
                raise RuntimeError(f"wheel metadata does not declare version {__version__}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target_dir), str(wheel)],
            check=True,
            cwd=root,
            capture_output=True,
            text=True,
        )
        source = workspace / "source"
        source.mkdir()
        (source / "guide.md").write_text("# Guide\nRetry policy and exact defaults.\n", encoding="utf-8")
        package = workspace / "package"
        cases = workspace / "cases.json"
        cases.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "reviewed": True,
                    "cases": [{"query": "retry policy", "expected_filepath": "guide.md", "reviewed": True}],
                }
            ),
            encoding="utf-8",
        )
        commands = [
            [
                sys.executable,
                "-m",
                "docops",
                "run",
                str(source),
                "--output",
                str(package),
                "--slug",
                "wheel",
                "--license",
                "MIT",
            ],
            [sys.executable, "-m", "docops", "validate", str(package), "--json"],
            [
                sys.executable,
                "-m",
                "docops",
                "evaluate",
                "--package",
                str(package),
                "--cases",
                str(cases),
                "--adapter",
                "memory",
                "--json",
            ],
        ]
        evaluation: dict[str, object] | None = None
        for command in commands:
            completed = subprocess.run(command, check=False, cwd=workspace, capture_output=True, text=True)
            if completed.returncode:
                raise RuntimeError(f"wheel end-to-end command failed: {command}: {command_failure_details(completed)}")
            if command[3] == "evaluate":
                parsed = json.loads(completed.stdout)
                if not isinstance(parsed, dict):
                    raise RuntimeError("wheel evaluation emitted an invalid JSON object")
                evaluation = parsed
        if evaluation is None or evaluation.get("ok") is not True:
            raise RuntimeError("wheel evaluation did not produce a successful result")
        metadata = evaluation.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("adapter") != "memory":
            raise RuntimeError(f"wheel evaluation did not report the memory adapter: {evaluation!r}")
        manifest_text = (package / "manifest.json").read_text(encoding="utf-8")
        if str(workspace) in manifest_text or str(PROJECT_ROOT) in manifest_text:
            raise RuntimeError("wheel package leaked a machine-local path into its manifest")
    print(
        json.dumps(
            {
                "ok": True,
                "wheel": wheel.name,
                "version": __version__,
                "adapter": "memory",
                "ragflow": "external-profile",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
