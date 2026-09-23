from __future__ import annotations

from pathlib import Path

from scripts.generate_supply_chain import generate


def test_supply_chain_resolves_relative_wheel_against_root(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    wheel = root / "dist" / "farol.whl"
    root.mkdir()
    wheel.parent.mkdir()
    wheel.write_bytes(b"wheel-fixture")
    (root / "requirements.lock").write_text("setuptools==84.0.0\n", encoding="utf-8")

    evidence = generate(
        root=root,
        wheel=Path("dist/farol.whl"),
        output=root / "artifacts" / "supply-chain",
    )

    assert evidence["ok"] is True
    assert evidence["wheel"]["path"] == "dist/farol.whl"
