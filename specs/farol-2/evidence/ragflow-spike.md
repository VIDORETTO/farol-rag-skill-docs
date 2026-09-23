# Receipt redigido — RAGFlow/Docling real — 2026-09-20

## Identidade fixada

- RAGFlow: `v0.27.2`.
- Commit upstream: `a024bea0cd93f39e6652a42bf84dd20c55bc560b`.
- Imagem: `infiniflow/ragflow@sha256:e6b3f1a185c0a70abb3a72e1092415df8c5c6a4fae0089545554f2936c4b27ab`.
- SDK Python: `ragflow-sdk==0.27.2`, Python 3.13.
- TEI: `infiniflow/text-embeddings-inference@sha256:ad4a00f5af757f7f323bdeb9e873313ed71225cf57d94658cbc9c6c17dc67d85`.
- Embedding: `BAAI/bge-small-en-v1.5` builtin/local.
- OCR local: `docling==2.129.0`, `onnxruntime==1.30.0`, RapidOCR.

## RAGFlow

`scripts/run_ragflow_profile.py --timeout 900 --json` terminou `passed` com
dois testes de integração executados e nenhum skip/failure.

| Operação | Resultado |
|---|---|
| health/auth | passed |
| dataset isolado | passed |
| upload PDF sintético | passed |
| parse terminal | passed |
| chunks/locators páginas 1 e 2 | passed |
| retrieval conhecido | passed |
| adapter prepare/apply/mapping/query | passed |
| citação canônica | passed |
| snapshot | passed |
| discard/rebuild | passed |
| equivalência canônica após rebuild | passed |
| cleanup e ausência dos datasets | passed |

O receipt emitido pelo spike contém somente hashes dos IDs/digest e contagens;
token, endpoint, IDs externos, caminho temporário e texto marcador não aparecem.

## OCR

`scripts/run_ocr_profile.py --timeout 900 --json` terminou `passed` com um teste
real executado, nenhum skip/failure. Um PDF raster sintético de duas páginas
produziu texto esperado, locators page+bbox finitos, confiança acima do limiar,
execução `local` e flag `ocr` pelo seam público `PdfExtractor`.

## Cleanup e limites

- Datasets temporários do spike e do adapter foram excluídos e sua ausência foi
  consultada pela API.
- O stack é exclusivamente de desenvolvimento, loopback-only, e será removido
  depois dos gates externos finais.
- A evidência prova contrato/lifecycle e fixtures pequenas; não é benchmark de
  capacidade ou autorização de produção/cutover.
