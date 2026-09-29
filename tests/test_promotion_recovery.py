from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import docops


def _request(
    source: Path,
    output: Path,
    *,
    mode: str,
    stale_lease_seconds: float = 0.05,
) -> docops.OperationRequest:
    return docops.OperationRequest(
        source,
        docops.OperationOptions(
            output_dir=output,
            source_root=source.parent,
            slug="guide",
            license="MIT",
            mode=mode,
            lease_policy="wait",
            lease_timeout_seconds=2.0,
            stale_lease_seconds=stale_lease_seconds,
        ),
    )


def test_next_public_operation_recovers_after_crash_between_promotion_renames(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    document = source / "guide.md"
    document.write_text("# Guide\nGeneration one.\n", encoding="utf-8")
    output = tmp_path / "package"
    initial = docops.apply(docops.plan(_request(source, output, mode="create")))
    assert initial.ok, initial.errors

    document.write_text("# Guide\nGeneration two.\n", encoding="utf-8")
    writer = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        import docops

        source = Path(sys.argv[1])
        output = Path(sys.argv[2])
        request = docops.OperationRequest(
            source,
            docops.OperationOptions(
                output_dir=output,
                source_root=source.parent,
                slug="guide",
                license="MIT",
                mode="update",
                lease_policy="wait",
                lease_timeout_seconds=2.0,
                stale_lease_seconds=0.05,
            ),
        )
        docops.apply(docops.plan(request))
        """
    )
    environment = {**os.environ, "DOCOPS_TEST_PROMOTION_FAILPOINT": "after-active-to-backup"}
    repository = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = str(repository) + os.pathsep + environment.get("PYTHONPATH", "")
    crashed = subprocess.run(
        [sys.executable, "-c", writer, str(source), str(output)],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert crashed.returncode == 86, crashed.stderr

    interrupted = docops.inspect(output)
    assert interrupted["recovery"]["status"] == "recoverable"
    assert interrupted["recovery"]["phase"] == "active-moved"

    resumed = docops.apply(docops.plan(_request(source, output, mode="update", stale_lease_seconds=300.0)))
    assert resumed.ok, resumed.errors
    assert (output / "rag" / "documents" / "guide.md").read_text(encoding="utf-8") == ("# Guide\nGeneration two.\n")

    stable = docops.inspect(output)
    assert stable["managed"] is True
    assert stable["active"]["validation"]["ok"] is True
    assert stable["recovery"]["status"] == "stable"
    assert not stable["backups"]


def test_next_public_operation_finalizes_a_crash_after_new_generation_install(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    document = source / "guide.md"
    document.write_text("# Guide\nGeneration one.\n", encoding="utf-8")
    output = tmp_path / "package"
    initial = docops.apply(docops.plan(_request(source, output, mode="create")))
    assert initial.ok, initial.errors

    document.write_text("# Guide\nGeneration two.\n", encoding="utf-8")
    writer = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        import docops

        source = Path(sys.argv[1])
        output = Path(sys.argv[2])
        request = docops.OperationRequest(
            source,
            docops.OperationOptions(
                output_dir=output,
                source_root=source.parent,
                slug="guide",
                license="MIT",
                mode="update",
                lease_policy="wait",
                lease_timeout_seconds=2.0,
                stale_lease_seconds=0.05,
            ),
        )
        docops.apply(docops.plan(request))
        """
    )
    environment = {**os.environ, "DOCOPS_TEST_PROMOTION_FAILPOINT": "after-stage-to-active"}
    repository = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = str(repository) + os.pathsep + environment.get("PYTHONPATH", "")
    crashed = subprocess.run(
        [sys.executable, "-c", writer, str(source), str(output)],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert crashed.returncode == 86, crashed.stderr

    interrupted = docops.inspect(output)
    assert interrupted["recovery"]["status"] == "recoverable"
    assert interrupted["recovery"]["phase"] == "active-installed"

    resumed = docops.apply(docops.plan(_request(source, output, mode="update", stale_lease_seconds=300.0)))
    assert resumed.ok, resumed.errors
    stable = docops.inspect(output)
    assert stable["active"]["validation"]["ok"] is True
    assert stable["recovery"]["status"] == "stable"
    assert not stable["backups"]


@pytest.mark.parametrize(
    ("failpoint", "expected_phase"),
    [
        ("after-active-to-backup-before-journal", "prepared"),
        ("after-stage-to-active-before-journal", "active-moved"),
    ],
)
def test_next_public_operation_recovers_when_process_dies_between_rename_and_journal_update(
    tmp_path: Path,
    failpoint: str,
    expected_phase: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    document = source / "guide.md"
    document.write_text("# Guide\nGeneration one.\n", encoding="utf-8")
    output = tmp_path / "package"
    assert docops.apply(docops.plan(_request(source, output, mode="create"))).ok
    document.write_text("# Guide\nGeneration two.\n", encoding="utf-8")
    writer = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        import docops

        source = Path(sys.argv[1])
        output = Path(sys.argv[2])
        request = docops.OperationRequest(
            source,
            docops.OperationOptions(
                output_dir=output,
                source_root=source.parent,
                slug="guide",
                license="MIT",
                mode="update",
                lease_policy="wait",
                lease_timeout_seconds=2.0,
                stale_lease_seconds=0.05,
            ),
        )
        docops.apply(docops.plan(request))
        """
    )
    environment = {**os.environ, "DOCOPS_TEST_PROMOTION_FAILPOINT": failpoint}
    repository = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = str(repository) + os.pathsep + environment.get("PYTHONPATH", "")

    crashed = subprocess.run(
        [sys.executable, "-c", writer, str(source), str(output)],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert crashed.returncode == 86, crashed.stderr
    interrupted = docops.inspect(output)
    assert interrupted["recovery"]["status"] == "recoverable"
    assert interrupted["recovery"]["phase"] == expected_phase
    resumed = docops.apply(docops.plan(_request(source, output, mode="update", stale_lease_seconds=300.0)))
    assert resumed.ok, resumed.errors
    assert (output / "rag" / "documents" / "guide.md").read_text(encoding="utf-8") == ("# Guide\nGeneration two.\n")
    stable = docops.inspect(output)
    assert stable["recovery"]["status"] == "stable"
    assert not stable["backups"]
