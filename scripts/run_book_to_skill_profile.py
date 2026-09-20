"""Run the external book-to-skill harness against a governed Farol projection.

The Farol core never invokes a model or reads the extracted corpus directly.
This profile exercises the external Agent Skill as an adapter: extraction and
taxonomy are created locally, only the approved IR projection is supplied to
the skill renderer, and the resulting skills are accepted through the public
SynthesisEngine validation seam.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from docops.extractors.base import ExtractorPolicy  # noqa: E402
from docops.extractors.text_web import TextWebExtractor  # noqa: E402
from docops.ir import IRBlock  # noqa: E402
from docops.revisions import content_hash  # noqa: E402
from docops.synthesis import SynthesisEngine  # noqa: E402
from docops.taxonomy import TaxonomyEngine, TaxonomyRevision  # noqa: E402

HARNESS_ENV = "FAROL_BOOK_TO_SKILL_ROOT"
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "documents" / "fixtures" / "acme-docs"
DEFAULT_PROJECT_REVISION = "farol-tk011-book-to-skill-2026-09-20"
DEFAULT_LANGUAGE = "pt-BR"


class ExternalBookToSkillAdapter:
    """Adapter boundary for output authored by the installed external skill."""

    name = "book-to-skill"
    execution = "external-harness"

    def __init__(self, version: str, output: Mapping[str, Any]) -> None:
        self.version = version
        self._output = dict(output)

    def synthesize(self, _request: Any, _projections: Mapping[str, list[IRBlock]]) -> Mapping[str, Any]:
        return self._output


def _discover_harness(explicit: Path | None) -> dict[str, Any] | None:
    candidates = []
    if explicit is not None:
        candidates.append(explicit.expanduser())
    else:
        env_value = os.environ.get(HARNESS_ENV, "").strip()
        if env_value:
            candidates.append(Path(env_value).expanduser())
        candidates.extend(
            [
                Path.home() / ".codex" / "skills" / "book-to-skill",
                Path.home() / ".agents" / "skills" / "book-to-skill",
            ]
        )
    seen: set[Path] = set()
    for candidate in candidates:
        root = candidate.resolve()
        if root in seen:
            continue
        seen.add(root)
        required = (
            root / "SKILL.md",
            root / "scripts" / "extract.py",
            root / "tools" / "validate_skill.py",
            root / "tools" / "scan_generated_skill.py",
        )
        if not all(path.is_file() for path in required):
            continue
        commit = _git_value(root, "rev-parse", "--verify", "HEAD")
        if not commit or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            continue
        license_path = next(
            (path for path in (root / "LICENSE.md", root / "LICENSE") if path.is_file()),
            None,
        )
        license_text = license_path.read_text(encoding="utf-8", errors="replace") if license_path else ""
        if "MIT License" not in license_text and "Permission is hereby granted" not in license_text:
            continue
        return {
            "root": root,
            "commit": commit,
            "license": "MIT",
            "extract": root / "scripts" / "extract.py",
            "validate": root / "tools" / "validate_skill.py",
            "scan": root / "tools" / "scan_generated_skill.py",
        }
    return None


def _git_value(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _run_extract(source_dir: Path, harness: Mapping[str, Any], workdir: Path) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["BOOK_SKILL_WORKDIR"] = str(workdir)
    command = [
        sys.executable,
        str(harness["extract"]),
        str(source_dir),
        "--mode",
        "text",
        "--install-missing",
        "no",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("book-to-skill extraction timed out") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"book-to-skill extraction failed: {completed.stderr[-2000:]}")
    metadata_path = workdir / "metadata.json"
    if not metadata_path.is_file():
        raise RuntimeError("book-to-skill extraction did not produce metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    text_path = Path(str(metadata.get("output_text") or workdir / "full_text.txt"))
    if not text_path.is_file():
        raise RuntimeError("book-to-skill extraction did not produce full_text.txt")
    return metadata


def _extract_ir(source_dir: Path) -> tuple[list[Any], list[IRBlock]]:
    extractor = TextWebExtractor()
    documents = []
    blocks: list[IRBlock] = []
    for path in sorted(source_dir.glob("*.md")):
        result = extractor.extract(
            path,
            ExtractorPolicy(
                rights_ref="fixture-MIT",
                source_id=f"acme-{path.stem}",
                source_revision_id="fixture-2026-09-20",
                required_fidelity="structured-native",
                purpose="farol-tk011-book-to-skill",
            ),
            {},
        )
        if result.document is None:
            raise RuntimeError(f"IR extraction returned no document for {path.name}")
        documents.append(result.document)
        blocks.extend(result.document.blocks)
    if len(documents) != 2 or not blocks:
        raise RuntimeError("the TK-011 fixture must produce two source documents and non-empty IR")
    return documents, blocks


def _taxonomy(documents: list[Any], blocks: list[IRBlock]) -> TaxonomyRevision:
    by_source = {document.source_id: document for document in documents}
    guide_blocks = by_source["acme-guide"].blocks
    release_blocks = by_source["acme-release"].blocks
    guide_intro = next(
        block for block in guide_blocks if block.kind == "paragraph" and block.heading_path == ["Acme API Guide"]
    )
    engine = TaxonomyEngine()
    proposal = engine.propose(
        blocks,
        goal="Operate the Acme client safely and evolve its request contract",
        project_revision=DEFAULT_PROJECT_REVISION,
        ir_revision=content_hash({"documents": [document.revision_hash() for document in documents]}),
        proposal={
            "nodes": [
                {
                    "node_id": "reliability",
                    "concept_id": "reliability",
                    "owner": "reliability",
                    "title": "Acme API Reliability",
                    "slug": "acme-api-reliability",
                    "coverage": [block.block_id for block in guide_blocks],
                    "cross_references": ["release"],
                },
                {
                    "node_id": "release",
                    "concept_id": "release",
                    "owner": "release",
                    "title": "Acme API Release Management",
                    "slug": "acme-api-release",
                    "coverage": [guide_intro.block_id, *(block.block_id for block in release_blocks)],
                    "cross_references": ["reliability"],
                },
            ]
        },
    )
    return engine.approve(proposal, {"approved": True, "actor": "book-to-skill-profile"})


def _block(blocks: Iterable[IRBlock], *, contains: str) -> IRBlock:
    for block in blocks:
        if contains.casefold() in (block.text or "").casefold():
            return block
    raise RuntimeError(f"fixture block not found: {contains}")


def _claim(claim_id: str, text: str, block: IRBlock) -> dict[str, Any]:
    return {"claim_id": claim_id, "text": text, "lineage": [{"block_id": block.block_id}]}


def _external_skill_output(blocks: list[IRBlock], language: str) -> dict[str, Any]:
    auth = _block(blocks, contains="Create a client with a bearer token")
    retries = _block(blocks, contains="Retry a transient")
    errors = _block(blocks, contains="Return a JSON error")
    timeout = _block(blocks, contains="timeout_seconds")
    reliability_main = f"""---
name: acme-api-reliability
description: "Princípios operacionais da API Acme para autenticação, retries e erros verificáveis."
license: MIT
---

# Acme API Reliability
**Author**: Acme synthetic documentation | **Sources**: 2 | **Generated**: 2026-09-20

## How to Use This Skill

- Use esta skill quando precisar operar o cliente Acme com comportamento previsível.
- Para mudanças de configuração e compatibilidade, consulte `acme-api-release`.
- A evidência factual permanece em inglês quando o termo original é relevante; a orientação está em {language}.

## Core Frameworks & Mental Models

- **Bearer authentication**: crie o cliente com um bearer token e envie-o no header `Authorization`.
- **Bounded exponential backoff**: faça retry apenas para respostas transitórias `429` ou `503`, com backoff exponencial limitado.
- **Stable error contract**: devolva erro JSON com `code` estável e `message` legível.
- **Security boundary**: nunca escreva credenciais de autenticação em fonte ou relatório.

## Chapter Index

| # | Title | Key Frameworks |
|---|-------|----------------|
| [ch01](chapters/ch01-authentication.md) | Autenticação bearer | `Authorization`, credencial efêmera |
| [ch02](chapters/ch02-retries-and-errors.md) | Retries e erros | `429`, `503`, backoff, contrato JSON |

## Topic Index

- **Authentication** → ch01
- **Authorization header** → ch01
- **Exponential backoff** → ch02
- **Retries** → ch02
- **Stable error code** → ch02

## Supporting Files

- [glossary.md](glossary.md) — termos essenciais
- [patterns.md](patterns.md) — técnicas operacionais
- [cheatsheet.md](cheatsheet.md) — decisões rápidas

## Scope & Limits

Esta skill deriva somente das fontes sintéticas aprovadas. Ela não substitui a IR, o router ou as citações canônicas.
"""
    release_main = """---
name: acme-api-release
description: "Regras de evolução da API Acme para timeout_seconds, defaults e mudanças compatíveis."
license: MIT
---

# Acme API Release Management
**Author**: Acme synthetic documentation | **Sources**: 2 | **Generated**: 2026-09-20

## How to Use This Skill

- Use esta skill ao avaliar mudanças de configuração do cliente.
- Consulte `acme-api-reliability` antes de alterar retries, autenticação ou erros.
- Preserve o termo original `timeout_seconds` para manter compatibilidade.

## Core Frameworks & Mental Models

- **Explicit timeout default**: `timeout_seconds` tem default de 10 segundos.
- **Scoped override**: callers podem substituir o timeout em uma única request sem mudar o default global.
- **Compatibility bridge**: mudanças de release devem preservar os contratos de operação e apontar para a skill de reliability.

## Chapter Index

| # | Title | Key Frameworks |
|---|-------|----------------|
| [ch01](chapters/ch01-timeout-option.md) | Opção de timeout | default, override, compatibilidade |

## Topic Index

- **Default** → ch01
- **timeout_seconds** → ch01
- **Single-request override** → ch01

## Supporting Files

- [glossary.md](glossary.md) — termos essenciais
- [patterns.md](patterns.md) — técnicas de evolução
- [cheatsheet.md](cheatsheet.md) — decisões rápidas

## Scope & Limits

Esta skill cobre somente a nota de release sintética e não autoriza publicar ou migrar corpus real.
"""
    reliability_chapter = """# Chapter 1: Autenticação bearer

## Core Idea

O cliente deve enviar a credencial efêmera no header `Authorization` sem persistir seu valor em fonte ou relatório.

## Frameworks Introduced

- **Bearer authentication**: use quando uma request precisa de identidade do cliente; envie o bearer token no header `Authorization`.

## Key Concepts

- **Bearer token**: credencial apresentada pelo cliente para autenticar a request.
- **Authorization**: header HTTP que transporta a credencial.

## Anti-patterns

- **Persistir o valor da credencial**: expõe material sensível e viola a fronteira de segurança.

## Key Takeaways

1. Crie o cliente com a credencial disponível somente no escopo da request.
2. Envie o termo original `Authorization` sem renomeá-lo.
3. Nunca copie o valor da credencial para documentação, source ou receipt.

## Connects To

- **Ch 2**: requests autenticadas ainda precisam de retry e erros determinísticos.
- **acme-api-release**: mudanças de timeout devem preservar o fluxo autenticado.
"""
    reliability_retry_chapter = """# Chapter 2: Retries e erros

## Core Idea

O cliente distingue falhas transitórias de erros permanentes e publica um contrato de erro estável.

## Frameworks Introduced

- **Bounded exponential backoff**: use para `429` e `503`; limite o crescimento do intervalo.
- **Stable error contract**: retorne JSON com `code` estável e `message` humano.

## Key Concepts

- **429**: resposta transitória de limitação.
- **503**: resposta transitória de indisponibilidade.
- **Stable code**: identificador que consumidores podem tratar sem depender do texto.

## Anti-patterns

- **Retry em erro de autenticação ou request malformada**: repete uma falha permanente e aumenta ruído.

## Key Takeaways

1. Faça retry apenas em `429` e `503`.
2. Use backoff exponencial limitado.
3. Mantenha `code` estável e `message` legível.

## Connects To

- **Ch 1**: autenticação inválida não é condição transitória.
- **acme-api-release**: opções novas não podem quebrar esse contrato.
"""
    release_chapter = """# Chapter 1: Opção de timeout

## Core Idea

O release 1.1.0 introduz `timeout_seconds` com default de 10 segundos e override por request.

## Frameworks Introduced

- **Explicit timeout default**: use o valor de 10 segundos quando o caller não informar override.
- **Scoped override**: altere o timeout somente para a request que precisa de outra duração.

## Key Concepts

- **timeout_seconds**: opção de configuração do cliente.
- **Default**: 10 segundos.
- **Override**: substituição local feita pelo caller.

## Anti-patterns

- **Alterar o default global para resolver uma request**: cria efeitos colaterais em callers não relacionados.

## Key Takeaways

1. Preserve o nome original `timeout_seconds`.
2. Use 10 segundos quando não houver override.
3. Faça overrides de forma local e explícita.

## Connects To

- **acme-api-reliability**: timeouts coexistem com retry e erro estável.
"""
    return {
        "skills": [
            {
                "topic_id": "reliability",
                "slug": "acme-api-reliability",
                "markdown": reliability_main,
                "chapters": {
                    "ch01-authentication.md": reliability_chapter,
                    "ch02-retries-and-errors.md": reliability_retry_chapter,
                },
                "claims": [
                    _claim("authentication-header", "O cliente envia bearer token no header Authorization.", auth),
                    _claim(
                        "transient-retry", "Apenas 429 e 503 recebem retry com backoff exponencial limitado.", retries
                    ),
                    _claim("stable-errors", "Erros JSON expõem code estável e message legível.", errors),
                ],
                "supporting": {
                    "glossary.md": """# Glossary\n\n**Authorization** — header que transporta a credencial (Ch 1).\n**Bearer token** — credencial apresentada pelo cliente (Ch 1).\n**Exponential backoff** — intervalo crescente e limitado para retry (Ch 2).\n**Stable code** — identificador estável do erro (Ch 2).\n""",
                    "patterns.md": """# Patterns\n\n## Bounded retry\n**When to use**: respostas 429 ou 503.\n**How**: aplique backoff exponencial com limite.\n**Trade-offs**: tolera transientes sem repetir falhas permanentes.\n\n## Stable error envelope\n**When to use**: toda falha publicada ao caller.\n**How**: retorne JSON com code e message.\n**Trade-offs**: facilita automação sem congelar o texto humano.\n""",
                    "cheatsheet.md": """# Cheatsheet\n\n| Situação | Decisão |\n|---|---|\n| 429 ou 503 | Retry com backoff exponencial limitado. |\n| Autenticação inválida | Não retry; corrija a credencial. |\n| Request malformada | Não retry; corrija o payload. |\n| Erro publicado | Inclua code estável e message legível. |\n""",
                },
            },
            {
                "topic_id": "release",
                "slug": "acme-api-release",
                "markdown": release_main,
                "chapters": {"ch01-timeout-option.md": release_chapter},
                "claims": [
                    _claim("timeout-default", "timeout_seconds tem default de 10 segundos.", timeout),
                    _claim("timeout-override", "O caller pode sobrescrever timeout_seconds em uma request.", timeout),
                ],
                "supporting": {
                    "glossary.md": """# Glossary\n\n**Default** — valor aplicado quando não há override (Ch 1).\n**Override** — substituição local para uma request (Ch 1).\n**timeout_seconds** — opção de timeout do cliente (Ch 1).\n""",
                    "patterns.md": """# Patterns\n\n## Scoped timeout override\n**When to use**: uma request precisa de duração diferente.\n**How**: informe timeout_seconds somente nessa request.\n**Trade-offs**: evita alterar comportamento global.\n""",
                    "cheatsheet.md": """# Cheatsheet\n\n| Necessidade | Decisão |\n|---|---|\n| Sem requisito especial | Use timeout_seconds=10. |\n| Uma request mais lenta | Faça override local. |\n| Mudança global | Não derive de uma única request. |\n""",
                },
            },
        ]
    }


def _write_supporting_files(root: Path, output: Mapping[str, Any]) -> list[Path]:
    written: list[Path] = []
    for skill in output["skills"]:
        skill_dir = root / "skills" / str(skill["slug"])
        for name, value in dict(skill.get("supporting", {})).items():
            path = skill_dir / name
            path.write_text(str(value), encoding="utf-8")
            written.append(path)
    return written


def _run_validator(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _tree_hash(root: Path) -> str:
    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return content_hash(entries)


def run_profile(
    *,
    source_dir: Path,
    harness_root: Path | None,
    output_root: Path | None,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    harness = _discover_harness(harness_root)
    if harness is None:
        return {
            "schema_version": 1,
            "ok": False,
            "status": "blocked",
            "reason": "harness_unavailable",
            "required": [
                "SKILL.md",
                "scripts/extract.py",
                "tools/validate_skill.py",
                "tools/scan_generated_skill.py",
                "MIT license",
                "git commit",
            ],
        }
    source_dir = source_dir.expanduser().resolve()
    if not source_dir.is_dir():
        return {"schema_version": 1, "ok": False, "status": "blocked", "reason": "source_fixture_missing"}
    retained = output_root is not None
    temporary_output: tempfile.TemporaryDirectory[str] | None = None
    if output_root is None:
        temporary_output = tempfile.TemporaryDirectory(prefix="farol-book-to-skill-")
        output_root = Path(temporary_output.name)
    else:
        output_root = output_root.expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix="farol-book-skill-extract-") as extraction_dir:
            metadata = _run_extract(source_dir, harness, Path(extraction_dir))
            documents, blocks = _extract_ir(source_dir)
            taxonomy = _taxonomy(documents, blocks)
            output = _external_skill_output(blocks, language)
            adapter = ExternalBookToSkillAdapter(str(harness["commit"]), output)
            engine = SynthesisEngine(adapter=adapter)
            candidate = engine.generate(
                taxonomy,
                blocks,
                language=language,
                budget={"max_tokens": 4000},
                request_id="tk011-book-to-skill-acme-20260920",
            )
            written = engine.write(candidate, output_root)
            written.extend(_write_supporting_files(output_root, output))

            validations: dict[str, Any] = {}
            for skill in candidate.skills:
                skill_dir = output_root / "skills" / skill.slug
                validations[skill.slug] = {
                    "validate": _run_validator([sys.executable, str(harness["validate"]), str(skill_dir / "SKILL.md")]),
                    "scan": _run_validator([sys.executable, str(harness["scan"]), str(skill_dir)]),
                    "files": len([path for path in skill_dir.rglob("*") if path.is_file()]),
                }
            valid = all(item["validate"]["ok"] and item["scan"]["ok"] for item in validations.values())
            claims = sum(len(skill.lineage) for skill in candidate.skills)
            return {
                "schema_version": 1,
                "ok": valid,
                "status": "passed" if valid else "failed",
                "profile": "book-to-skill",
                "execution": "external-harness",
                "harness": {"name": harness["root"].name, "commit": harness["commit"], "license": harness["license"]},
                "extraction": {
                    "sources": [
                        {"filename": item.get("filename"), "format": item.get("format"), "words": item.get("words")}
                        for item in metadata.get("sources", [])
                    ],
                    "total_sources": metadata.get("total_sources"),
                    "words": metadata.get("words"),
                    "estimated_tokens": metadata.get("estimated_tokens"),
                    "metadata_hash": hashlib.sha256(
                        json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                },
                "ir": {
                    "documents": len(documents),
                    "blocks": len(blocks),
                    "revision": content_hash({"documents": [document.revision_hash() for document in documents]}),
                    "projection": "topic-scoped blocks only; source originals were not passed to synthesis",
                },
                "taxonomy": {
                    "revision": taxonomy.revision_id,
                    "topics": [node.slug for node in taxonomy.nodes],
                    "coverage_ratio": taxonomy.coverage.get("coverage_ratio"),
                    "overlaps": len(taxonomy.overlaps),
                },
                "synthesis": {
                    "request_hash": candidate.receipt.request_hash,
                    "input_hash": candidate.receipt.input_hash,
                    "output_hash": candidate.receipt.output_hash,
                    "skills": [skill.slug for skill in candidate.skills],
                    "token_counts": {skill.slug: skill.token_count for skill in candidate.skills},
                    "lineage_claims": claims,
                    "lineage_blocks": sum(len(item.block_refs) for skill in candidate.skills for item in skill.lineage),
                    "receipt": candidate.receipt.to_dict(),
                },
                "validation": validations,
                "output": {
                    "tree_hash": _tree_hash(output_root),
                    "file_count": len(written),
                    "retained": retained,
                },
                "external_state_changed": False,
            }
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        return {
            "schema_version": 1,
            "ok": False,
            "status": "failed",
            "profile": "book-to-skill",
            "reason": "profile_execution_failed",
            "error": str(exc),
        }
    finally:
        if temporary_output is not None:
            temporary_output.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--harness-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--json", action="store_true", help="emit one machine-readable report")
    args = parser.parse_args(argv)
    report = run_profile(
        source_dir=args.source_dir,
        harness_root=args.harness_root,
        output_root=args.output,
        language=args.language,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report.get("status") == "passed":
        return 0
    if report.get("status") == "blocked":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
