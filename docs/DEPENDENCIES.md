# Dependências, atualizações e suporte

O núcleo `docops` não possui dependências de runtime além da biblioteca padrão
do Python. Os perfis opcionais declarados em `pyproject.toml` são:

- `formats`: `PyYAML==6.0.3`, `pypdf==6.16.2` e `python-docx==1.2.0`;
- `ragflow`: `ragflow-sdk==0.27.2`, somente no interpretador Python 3.13;
- `ocr`: `docling==2.129.0` e `onnxruntime==1.30.0`, também no perfil Python
  3.13, com RapidOCR fornecido pelo fluxo Docling;
- `dev`: `pytest==9.1.1`, `ruff==0.12.7`, `pip-audit==2.10.1` e
  `setuptools==84.0.0`.

O RAGFlow é um backend externo e opt-in. Ele não faz parte do lock direto do
core nem é iniciado ao importar `docops`. O perfil de integração exige endpoint,
bearer token, SDK compatível e imagem RAGFlow fixada por digest SHA-256. O
arquivo [`config/ragflow/dev-lock.json`](../config/ragflow/dev-lock.json) fixa
o upstream e os serviços auxiliares do ambiente local.

As versões diretas do core aparecem em `pyproject.toml`,
`requirements-dev.txt` e `requirements.lock`. O lock é uma lista exata de
raízes diretas, não um lock transitivo com hashes; a resolução transitiva é
observada e registrada por ambiente nos artefatos de supply-chain.

## Política de atualização

Dependências diretas só podem mudar com atualização simultânea do contrato de
instalação, testes, changelog e auditoria. Em cada candidato, execute:

```text
python -m pip check
python -m pip_audit --requirement requirements.lock --format json
python scripts/audit_dependencies.py --requirements requirements.lock --local --strict \
  --evidence-dir artifacts/dependency-audit
```

O gate falha para qualquer advisory não tratado pela política vigente. A
versão 2.0 não carrega mais `knowledge-rag`, `chromadb` ou o vendor legado; não
há allowlist de CVEs do Chroma no lock atual. Referências a esse risco em
documentos de auditoria anteriores são históricas e não descrevem o artefato
2.0.

## Perfis de integração

Para o perfil RAGFlow/OCR, use um ambiente Python 3.13 separado do core:

```text
python -m pip install --editable ".[dev,formats,ragflow,ocr]"
python scripts/run_release_gates.py --profile ragflow --json
python scripts/run_release_gates.py --profile full --timeout 3600 --json
```

Ausência de endpoint, token, digest, SDK ou serviço externo é registrada como
`blocked`/`not_run`; nunca como aprovação. A troca do perfil de embedding exige
`full_rebuild` e evidência nova antes de qualquer promoção.

## Plataformas

O alvo declarado é Python 3.11–3.13 em Ubuntu, Windows e macOS. Python 3.14 é
somente tolerado localmente. A matriz normativa está em
[`docs/SUPPORT-MATRIX.json`](SUPPORT-MATRIX.json) e é validada por
`scripts/check_support_matrix.py`.

O core foi exercitado no host Windows; CI e gates isolados cobrem os perfis
declarados. A integração RAGFlow e o OCR possuem execução própria e só podem
ser anunciados quando os recibos reais correspondentes estiverem presentes.

## Evidência do candidato

O bundle de supply-chain não distribui corpus, cache de modelo, tokens ou
credenciais. Para gerar e verificar a evidência de um wheel:

```text
python scripts/generate_supply_chain.py --root . --wheel dist/<wheel>.whl \
  --output artifacts/supply-chain --profile core
python scripts/verify_supply_chain.py --root . --evidence artifacts/supply-chain
```

O perfil `ragflow` pode ser gerado separadamente quando o SDK e o ambiente
externo estiverem provisionados. A evidência deve registrar o commit de origem,
o digest do candidato, o lock, o wheel e a procedência do runtime observado.

O gate full de 20 de setembro de 2026 passou 25/25 etapas, com 1045 comandos
aprovados, 12 skips explícitos e zero falhas, bloqueios ou etapas `not_run`.
