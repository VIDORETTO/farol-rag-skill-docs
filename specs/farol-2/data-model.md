# Modelo de dados alvo — Farol 2.0

Este documento detalha o plano; `spec.md` continua sendo a autoridade do
comportamento.

## Identidades e relações

```text
KnowledgeProject 1──* Source
Source           1──* SourceRevision
SourceRevision   1──* SourceArtifact
SourceArtifact   1──1 ExtractionReceipt
ExtractionReceipt 1──1 IRDocument
IRDocument       1──* IRBlock
TaxonomyRevision *──* IRBlock       (coverage/evidence)
SkillRevision    *──* IRBlock       (conceptual lineage)
IndexRevision    *──* IRBlock       (backend mapping)
Composition      1──1 IRRevision
Composition      1──1 TaxonomyRevision
Composition      1──* SkillRevision
Composition      1──1 RouterRevision
Composition      1──1 IndexRevision
```

Identidades canônicas são hashes de conteúdo e contexto contratual. Dataset,
document e chunk IDs do RAGFlow vivem apenas em `BackendMapping`.

## IRDocument

Campos mínimos:

- `schema_version`, `document_id`, `source_id`, `source_revision_id`;
- `artifact_id`, `content_hash`, `media_type`, `language`;
- `extractor`: nome, versão, execução local/remota e receipt;
- `fidelity`: nível, capacidades preservadas, degradações e confiança;
- `rights_ref`, `captured_at`, `effective_at`, `region`;
- lista ordenada de `blocks` e inventário de assets privados.

## IRBlock

Campos mínimos:

- `block_id`, `parent_id`, `ordinal`, `kind`;
- `text` ou representação estruturada segura;
- `heading_path` e `symbol` quando aplicável;
- locators: `line`, `page`, `bbox`, `slide`, `sheet`, `cell`, `timestamp`;
- `language`, `confidence`, `quality_flags`;
- `source_fragment_hash` para verificação sem publicar o original.

Kinds iniciais: `title`, `heading`, `paragraph`, `list`, `table`, `table_row`,
`code`, `quote`, `figure`, `caption`, `equation`, `metadata`.

## Taxonomia e skills

`TaxonomyRevision` possui nodes hierárquicos, ownership, aliases, dependências,
coverage obrigatória e refs de IR. `SkillRevision` possui budget, idioma,
arquivos, concepts e um sidecar de lineage. Um concept tem exatamente um owner;
refs cruzadas apontam ao owner.

## BackendMapping e IndexRevision

`BackendMapping` relaciona IDs canônicos a dataset/document/chunk IDs externos,
parser fingerprint e timestamps. `IndexRevision` fixa backend/version/digest,
embedding, parser/chunking/retrieval fingerprints, contagens e snapshot de
prontidão. Mudança de fingerprint exige candidata e rebuild compatível.

## Estados

```text
source: proposed → authorized → acquired → extracted → active
                                      └→ degraded | quarantined | failed
candidate: preparing → ready → evaluated → approved → active
                         └→ blocked | rejected
backend: unavailable → healthy → ingesting → indexed → queryable
```

Revogação é tombstone, não deleção histórica. Uma composição só é ativa
quando todas as suas revisões coordenadas são válidas e o backend está
`queryable`.
