# seam-scope: implementation-infrastructure (release artifact scripts: SBOM, checksums, workflow, container)
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_sbom import build_sbom, verify_checksums, write_checksums  # noqa: E402


def test_sbom_lists_the_distribution_and_its_installed_dependencies() -> None:
    sbom = build_sbom("farol-kit")

    names = {component["name"].casefold() for component in sbom["components"]}
    assert sbom["bomFormat"] == "CycloneDX" and sbom["specVersion"] == "1.5"
    assert sbom["metadata"]["component"]["name"] == "farol-kit"
    assert {"pyyaml", "pypdf", "python-docx"} <= names
    assert all(component["purl"].startswith("pkg:pypi/") for component in sbom["components"])


def test_checksums_detect_any_changed_artifact(tmp_path: Path) -> None:
    (tmp_path / "farol_kit-3.0.0-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "farol_kit-3.0.0.tar.gz").write_bytes(b"sdist")

    write_checksums(tmp_path)
    ok = verify_checksums(tmp_path)
    (tmp_path / "farol_kit-3.0.0.tar.gz").write_bytes(b"tampered")
    tampered = verify_checksums(tmp_path)

    assert ok == {"ok": True, "mismatches": []}
    assert tampered["mismatches"] == ["farol_kit-3.0.0.tar.gz"]


def test_release_workflow_publishes_with_trusted_publishing_and_provenance() -> None:
    import yaml

    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    assert workflow.get("permissions", {}) == {"contents": "read"}
    publish = jobs["publish-pypi"]
    assert publish["permissions"]["id-token"] == "write" and publish["environment"]["name"] == "pypi"
    assert jobs["attest"]["permissions"]["id-token"] == "write"  # Sigstore signing uses OIDC
    signing = {"publish-pypi", "attest"}
    assert all("id-token" not in (job.get("permissions") or {}) for name, job in jobs.items() if name not in signing)
    steps = [step.get("uses", "") for job in jobs.values() for step in job["steps"]]
    assert any(uses.startswith("actions/attest-build-provenance@") for uses in steps)
    assert all("@" in uses and len(uses.split("@")[1].split()[0]) == 40 for uses in steps if uses)


def test_container_runs_as_non_root_and_serves_mcp() -> None:
    text = (ROOT / "Containerfile").read_text(encoding="utf-8")

    assert "USER farol" in text and 'ENTRYPOINT ["farol"]' in text
    assert 'CMD ["mcp", "--project", "/knowledge"]' in text
    json.loads("{}")


def test_github_release_does_not_wait_for_an_unconfigured_pypi() -> None:
    import yaml

    jobs = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))["jobs"]

    assert "publish-pypi" not in jobs["github-release"]["needs"]
    assert "vars.PYPI_PUBLISH == 'true'" in jobs["publish-pypi"]["if"]
