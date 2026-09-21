# Harnesses e contrato de integração

O Farol entrega Agent Skills, router, corpus normalizado e um manifesto de
handoff. O arquivo `harness.json` é relativo e descreve o adapter externo
RAGFlow; ele não contém endpoint, token ou caminho pessoal.

## Estado verificado em 20 de setembro de 2026

| Componente | Versão | Resultado |
|---|---:|---|
| Agent Skill externo `book-to-skill` | commit `526f362552562d88c1a8bbf8012d2cee93f831d5` | duas skills reais, lineage, validator e scan aprovados |
| RAGFlow | `0.27.2` | health, dataset, upload, parse, chunks, retrieval, rebuild e cleanup aprovados |
| Docling + RapidOCR | `2.129.0` + ONNX Runtime `1.30.0` | PDF escaneado de duas páginas aprovado |
| Release gate full | árvore candidata baseada em `93bb8894d816aad3c3b3682ccec317db1da39d45` | `25/25`, `1045 passed`, `12 skipped`, zero falhas/bloqueios |

Os testes não publicam, fazem commit, iniciam modelos no core nem armazenam
credenciais. Integrações externas ausentes permanecem `blocked`/`not_run`.

## Passos comuns

1. Prepare somente as dependências do core com `python scripts/bootstrap.py --dev`.
2. Gere um pacote com `python -m docops run <fonte> --output <pacote> --license <id>`.
3. Carregue `<pacote>/skill` e `<pacote>/router` no harness de Agent Skills.
4. Para RAG factual, instale os extras em Python 3.13 e configure fora do repositório:

```text
DOCOPS_RAGFLOW_ENDPOINT=https://...
DOCOPS_RAGFLOW_TOKEN=<secret>
DOCOPS_RAGFLOW_IMAGE_DIGEST=<repository>@sha256:<64-hex>
DOCOPS_RAGFLOW_SDK_VERSION=0.27.2
```

5. Execute `python scripts/run_release_gates.py --profile ragflow --json`.

O core não inicia RAGFlow automaticamente. O perfil de desenvolvimento usa
loopback explícito; qualquer endpoint remoto exige HTTPS. `harness.json` mantém
somente identidade do adapter, versão, capacidades e `config.yaml` relativo.

## Handoff

O harness externo escolhe o modelo e produz a resposta final. O Farol fornece
as skills, o router e evidências com locators canônicos. Afirmações factuais
devem citar `path#secao`, `path:linha` ou locator equivalente; sem evidência
elegível, o resultado deve ser abstenção ou conflito.

O contrato canônico está em `schemas/harness.schema.json`. A decisão de
publicação continua manual e não é concedida pelo manifesto.

O snapshot versionado em `farol-v3` contém esse mesmo estado de implementação;
o commit da branch não altera o resultado dos recibos de 20 de setembro. A
publicação da versão 2.0 ainda depende de revisão humana, tag e release
explícitas.
