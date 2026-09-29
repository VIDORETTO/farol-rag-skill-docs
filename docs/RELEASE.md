# Release runbook (Farol 3)

Publishing is a maintainer decision: nothing is tagged, uploaded or announced
automatically. The 2.0 runbook and its evidence history are archived in
[archive/2.0/RELEASE-2.0.md](archive/2.0/RELEASE-2.0.md).

## 1. Everyday release gate

From a clean checkout of the commit to release:

```text
python scripts/bootstrap.py --dev
python scripts/run_release_gates.py --profile release --json
python scripts/acceptance_real.py --json
```

The `release` profile runs ten essential stages (doctor, contracts,
documentation, security, dependency audit, tests, lint, format, wheel, clean
clone). The acceptance corpus is downloaded by hash and reports `not_run` for
sources that cannot be reached from the machine (for example YouTube from a
datacenter IP). Record the results in `specs/farol-3/evidence/`.

## 2. Full matrix (before a major or minor release)

Run from a clean checkout; missing external services stay `blocked`/`not_run`
and never count as success:

```text
python -m docops doctor --json
python -m pip check
python -m pip_audit --requirement requirements.lock --format json
python scripts/audit_dependencies.py --requirements requirements.lock --local --strict
python scripts/check_support_matrix.py --json
python scripts/check_contracts.py --json
python scripts/check_documentation.py --json
python scripts/check_acceptance_matrix.py --check --json
python scripts/check_public_seams.py --json
python scripts/check_farol_v2_surface.py --surface all \
  --allow-path tests/test_cutover_dual.py
python scripts/check_error_catalog.py --json
python scripts/check_public_surface.py
python scripts/gen_reference.py --check
python -m pytest -q
python -m ruff check docops tests scripts
python -m ruff format --check docops tests scripts
python scripts/verify_clean_clone.py
python scripts/verify_wheel.py
python scripts/generate_supply_chain.py --root . --wheel dist/<wheel>.whl \
  --output artifacts/supply-chain --profile core
python scripts/verify_supply_chain.py --root . --evidence artifacts/supply-chain
python scripts/prepare_candidate.py --root . --output artifacts/candidate --profile core
python scripts/verify_candidate.py --root artifacts/candidate --source-root .
python scripts/audit_release.py --candidate --json
python scripts/run_release_gates.py --profile core --timeout 3600 --json
python scripts/run_release_gates.py --profile book-to-skill --timeout 3600 --json
python scripts/run_release_gates.py --profile ragflow --timeout 3600 --json
python scripts/run_release_gates.py --profile full --timeout 3600 --json
```

## 3. One-time repository setup

1. **PyPI trusted publisher**: on pypi.org, add a pending publisher for project
   `farol-kit`, owner `VIDORETTO`, repository `farol-rag-skill-docs`, workflow
   `release.yml`, environment `pypi`.
2. **GitHub environment** `pypi` with required reviewers (the maintainer).
   Then set the repository variable `PYPI_PUBLISH=true`; until it is set, a
   tag creates the GitHub release (wheel, sdist, SBOM, checksums, provenance)
   and skips PyPI.
3. **GitHub Pages**: Settings → Pages → Source: GitHub Actions (used by
   `.github/workflows/docs.yml` on pushes to `main`).

## 4. Publish

1. Update `pyproject.toml`, `docops/__init__.py`, `docs/REPOSITORY-METADATA.json`,
   `README.md` (`**Version:**`), `CHANGELOG.md` and `docs/RELEASE-NOTES-<version>.md`.
2. Merge to `main` through a reviewed pull request with green CI.
3. Tag and push: `git tag -s v<version> -m "Farol <version>"` then
   `git push origin v<version>`.
4. The `Release` workflow builds the wheel and sdist, installs them in a clean
   environment, writes a CycloneDX SBOM and `SHA256SUMS`, attests provenance,
   creates the GitHub release with the notes file and, when `PYPI_PUBLISH` is
   `true`, publishes to PyPI after the `pypi` environment approval.

## 5. Verify what was published

```text
pipx install farol-kit==<version>   # or: pipx install "farol-kit @ git+https://github.com/VIDORETTO/farol-rag-skill-docs@v<version>"
farol doctor
gh attestation verify farol_kit-<version>-py3-none-any.whl --repo VIDORETTO/farol-rag-skill-docs
python scripts/build_sbom.py verify --directory <downloaded-release-assets>
```

Never include private documents, acquired corpora, indexes, caches, models,
tokens or local paths in a release.
