import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from scripts.prepare_candidate import _build_wheel
from scripts.verify_candidate import _wheel_surface_errors

REQUIRED_RELEASE_ASSETS = {
    ".github/CODEOWNERS",
    "CHANGELOG.md",
    "community/CODEOWNERS",
    "community/PULL_REQUEST_TEMPLATE.md",
    "community/issue-templates/bug_report.yml",
    "community/issue-templates/feature_request.yml",
    "docs/DEPENDENCIES.md",
    "docs/RELEASE.md",
    "docs/RELEASE-NOTES-2.0.0-rc.1.md",
    "docs/SUPPORT-MATRIX.json",
}


def test_candidate_wheel_build_is_byte_reproducible(tmp_path: Path) -> None:
    first = _build_wheel(Path.cwd(), Path(sys.executable), tmp_path / "first")
    second = _build_wheel(Path.cwd(), Path(sys.executable), tmp_path / "second")

    assert first.read_bytes() == second.read_bytes()


def test_candidate_wheel_ignores_stale_build_lib_modules_and_audits_them(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    repository = Path.cwd()
    for filename in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(repository / filename, project / filename)
    for directory in ("docops", "skills"):
        shutil.copytree(
            repository / directory,
            project / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    stale_modules = (
        "docops/mcp_client.py",
        "docops/rag_sync.py",
        "docops/backends/legacy_knowledge_rag.py",
    )
    for relative in stale_modules:
        path = project / "build" / "lib" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# stale ignored build output\n", encoding="utf-8")

    wheel = _build_wheel(project, Path(sys.executable), tmp_path / "wheel")
    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())
    assert not members.intersection(stale_modules)
    assert _wheel_surface_errors(wheel) == []

    contaminated = tmp_path / "contaminated.whl"
    with zipfile.ZipFile(wheel) as source, zipfile.ZipFile(contaminated, "w", zipfile.ZIP_DEFLATED) as target:
        for member in source.namelist():
            target.writestr(member, source.read(member))
        target.writestr(stale_modules[0], "# removed legacy module\n")

    assert [item["code"] for item in _wheel_surface_errors(contaminated)] == ["wheel_legacy_module_present"]


def test_candidate_bundle_has_new_identity_and_reproducible_release_assets(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prepare_candidate.py",
            "--root",
            ".",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["ok"] is True
    assert report["version"] != "1.0.0"
    manifest = json.loads((output / "candidate-manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == report["version"]
    assert manifest["source_commit"]
    assert manifest["source_candidate_digest"]
    assert manifest["candidate_audit"]["ok"] is True
    assert any(path.endswith(".whl") for path in manifest["assets"])
    assert "evidence/sbom.json" in manifest["assets"]
    assert "README.md" in manifest["assets"]
    assert "community/CODE_OF_CONDUCT.md" in manifest["assets"]
    assert (output / "SHA256SUMS").is_file()

    verified = subprocess.run(
        [sys.executable, "scripts/verify_candidate.py", "--root", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stdout

    wheel = output / Path(manifest["wheel"]["path"])
    wheel.write_bytes(b"tampered candidate wheel")
    tampered = subprocess.run(
        [sys.executable, "scripts/verify_candidate.py", "--root", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert tampered.returncode == 1
    assert "digest" in tampered.stdout.casefold()

    metadata_path = output / "metadata" / "repository.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["version"] = "0.0.0"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    inconsistent = subprocess.run(
        [sys.executable, "scripts/verify_candidate.py", "--root", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert inconsistent.returncode == 1
    assert "metadata_version_mismatch" in inconsistent.stdout


def test_candidate_bundle_excludes_private_originals_and_runtime_state(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prepare_candidate.py",
            "--root",
            ".",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    manifest = json.loads((output / "candidate-manifest.json").read_text(encoding="utf-8"))
    assets = set(manifest["assets"])
    private_roots = {".docops", "artifacts", "data", "documents", "models_cache"}

    assert not any(Path(asset).parts and Path(asset).parts[0] in private_roots for asset in assets)
    assert not (output / "documents").exists()
    assert not (output / "data").exists()
    assert not (output / "models_cache").exists()
    assert (output / "provenance" / "requirements.lock").is_file()
    assert (output / "evidence" / "supply-chain.json").is_file()
    assert manifest["candidate_audit"]["ok"] is True
    assert manifest["publication"] == {
        "performed": False,
        "automated": False,
        "human_authorization_required": True,
        "actions": [],
    }


def test_candidate_verifier_requires_every_release_and_community_asset(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    prepared = subprocess.run(
        [sys.executable, "scripts/prepare_candidate.py", "--root", ".", "--output", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr

    manifest_path = output / "candidate-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["assets"] = [asset for asset in manifest["assets"] if asset not in REQUIRED_RELEASE_ASSETS]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "scripts/verify_candidate.py", "--root", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    missing = {
        error["message"].removeprefix("required candidate asset is missing: ")
        for error in payload["errors"]
        if error["code"] == "asset_required"
    }
    assert REQUIRED_RELEASE_ASSETS <= missing


def test_candidate_verifier_rejects_readme_version_drift(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    prepared = subprocess.run(
        [sys.executable, "scripts/prepare_candidate.py", "--root", ".", "--output", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    manifest = json.loads((output / "candidate-manifest.json").read_text(encoding="utf-8"))

    readme_path = output / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    readme_path.write_text(
        readme.replace(f"`{manifest['version']}`", "`9.9.9`", 1),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "scripts/verify_candidate.py", "--root", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert any(error["code"] == "readme_version_mismatch" for error in payload["errors"])


def test_candidate_verifier_rejects_changelog_version_drift(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    prepared = subprocess.run(
        [sys.executable, "scripts/prepare_candidate.py", "--root", ".", "--output", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    manifest = json.loads((output / "candidate-manifest.json").read_text(encoding="utf-8"))

    changelog_path = output / "CHANGELOG.md"
    changelog = changelog_path.read_text(encoding="utf-8")
    changelog_path.write_text(
        changelog.replace(f"## {manifest['version']}", "## 9.9.9", 1),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "scripts/verify_candidate.py", "--root", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert any(error["code"] == "changelog_version_mismatch" for error in payload["errors"])


def test_candidate_verifier_rejects_code_version_drift(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    prepared = subprocess.run(
        [sys.executable, "scripts/prepare_candidate.py", "--root", ".", "--output", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    manifest = json.loads((output / "candidate-manifest.json").read_text(encoding="utf-8"))
    wheel_path = output / manifest["wheel"]["path"]

    rewritten = wheel_path.with_suffix(".rewritten.whl")
    with zipfile.ZipFile(wheel_path) as source, zipfile.ZipFile(rewritten, "w") as destination:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "docops/__init__.py":
                data = data.replace(
                    f'__version__ = "{manifest["version"]}"'.encode(),
                    b'__version__ = "9.9.9"',
                )
            destination.writestr(info, data)
    rewritten.replace(wheel_path)

    completed = subprocess.run(
        [sys.executable, "scripts/verify_candidate.py", "--root", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert any(error["code"] == "code_version_mismatch" for error in payload["errors"])


def test_rag_candidate_records_model_provenance_without_distributing_model_cache(tmp_path: Path) -> None:
    model_cache = tmp_path / "private-model-cache"
    model_cache.mkdir()
    (model_cache / "embedding.onnx").write_bytes(b"reviewed-model-snapshot")
    output = tmp_path / "candidate"

    prepared = subprocess.run(
        [
            sys.executable,
            "scripts/prepare_candidate.py",
            "--root",
            ".",
            "--output",
            str(output),
            "--model-cache",
            str(model_cache),
            "--require-model",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    evidence = json.loads((output / "evidence" / "supply-chain.json").read_text(encoding="utf-8"))
    model = evidence["models"][0]
    assert model["status"] == "verified-external-snapshot"
    assert model["included"] is False
    assert model["path"] is None
    assert model["sha256"]
    assert model["files"]
    assert not (output / "provenance" / "model-cache").exists()
    assert not any("models_cache" in path.as_posix() or "model-cache" in path.as_posix() for path in output.rglob("*"))

    prohibited = output / "provenance" / "model-cache"
    prohibited.mkdir()
    (prohibited / "model.onnx").write_bytes(b"must-not-ship")
    verified = subprocess.run(
        [sys.executable, "scripts/verify_candidate.py", "--root", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 1
    assert "prohibited_model_cache" in verified.stdout
