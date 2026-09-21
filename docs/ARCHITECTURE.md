# Arquitetura e fronteiras

## O que este projeto faz

```text
entrada (nome | URL | repo | pasta)
             |
     resolução segura
             |
   plan (sem efeitos) ----> plano imutável + diff + políticas
             |
   apply --> staging + validação --> promoção transacional
             |
       IR canônica + skill + router + rag/documents
             |
        RAGFlow externo (opt-in, reconstruível)
             |
 harness externo decide como carregar contexto e qual modelo usar
```

Operações contínuas seguem a mesma fronteira: `source register/reconcile` →
evento idempotente → worker com lease → candidata → avaliação → aprovação →
publicação. Conversa e feedback entram apenas como proposta/sinal em
quarentena; `reader-session` fixa uma geração e snapshot RAG read-only, e
revogação invalida derivados, snapshots, readers e rollback dependentes.

O comando `docops` é determinístico nas partes sob seu controle. Ele não
interpreta a documentação como instruções executáveis e não chama modelos.
`book-to-skill` continua sendo uma Agent Skill executada pelo harness: pode
enriquecer o scaffold estrutural produzido pelo operador, mas o caminho base
não depende de uma sessão de chat nem de copiar e colar.

Extractors produzem uma IR canônica antes da síntese ou indexação. A IR é a
autoridade de identidade e preserva blocos, relações, ranges e locators; IDs ou
chunks emitidos pelo RAGFlow são mapeamentos reconstruíveis, não substitutos da
identidade canônica.

Na web, o `WebAcquirer` consulta `robots.txt` (incluindo `Sitemap:`), respeita
regras `Disallow`, tenta sitemaps antes da navegação interna e aplica limites de
host, páginas, profundidade, payload, timeout e redirects.

## Artefato público

Cada execução bem-sucedida cria:

- config.yaml: configuração stdio relativa ao pacote; é criada no primeiro run
  e preservada quando já existe uma configuração customizada;

- `manifest.json`: versão do contrato, outcome terminal, identidade da fonte, candidatos,
  licença/proveniência, entradas aceitas/ignoradas/erro, métricas e checkpoints;
- `skill/`: `SKILL.md`, capítulos, glossário, padrões e cheatsheet;
- `router/`: regra para separar orientação conceitual de fatos literais RAG;
- `rag/documents/`, `rag/sources.json` e `rag/index.json`: corpus normalizado e
  estado pronto para o backend;
- `harness.json`: registro MCP stdio com caminhos relativos para o host externo.
- `.docops/`: state, plano, recibos de fase, tentativas falhas e evidências de
  readiness; esse diretório é operacional e não deve ser publicado com corpus.

O pacote só é considerado consultável quando
`python -m docops validate <pacote>` passa. `corpus-ready` significa que os
documentos e metadados estão prontos; `indexed` significa que a integração
RAGFlow externa executou e registrou suas estatísticas. Sem endpoint, token,
digest e SDK compatíveis, o perfil permanece `blocked`/`not_run`.

Os schemas canônicos ficam em `schemas/` e a cópia `docops/schemas/` é gerada
por `scripts/sync_schemas.py`; a política de compatibilidade expand-contract
está em `docs/CONTRACT-COMPATIBILITY.md`.

## Estado e recuperação

`StateStore` usa `canonical + version` como chave lógica e inclui o hash no
identity. Escritas de JSON e texto são temporárias, sincronizadas e trocadas
com `os.replace`. `CheckpointStore` grava recibos com identidade do plano,
hash de entrada/saída, schema, duração e caminhos; repetir a execução só
reutiliza fases cujo recibo ainda coincide.

Cada pacote possui um lease local recuperável. Writers concorrentes falham ou
aguardam conforme `lease_policy`; o owner é redigido e nenhum processo global é
encerrado. A interface pública `docops.inspect()` espera a estabilização de um
writer vivo antes de devolver uma geração, preservando a geração ativa para
readers durante staging. A promoção troca diretórios no mesmo volume e restaura
o backup se a validação pós-promoção falhar; não é um lock distribuído. Readers
que acessam o filesystem diretamente podem observar uma janela de troca
específica da plataforma; o produto não promete atomicidade universal.

O core não inicia containers nem faz rede. A integração RAGFlow só é acionada
por um perfil externo autorizado, com endpoint, bearer token, SDK `0.27.2` e
imagem fixada por digest. O cliente controla somente os processos filhos que
abriu e não usa comandos globais para matar processos Python. O manifesto e a
avaliação registram backend, versão, perfil, corpus, locators e procedência.

O avaliador mantém os adapters lexical e em memória como diagnósticos/TDD. O
gate de release usa o adapter MCP com um pacote realmente indexado e registra
perfil, corpus, top-k, locators, lineage e resultados.

Antes do primeiro rename, `apply()` grava um journal local de promoção com o
nome do staging, backup, hash do plano e fase (`prepared`, `active-moved` ou
`active-installed`). Se o processo morrer entre os renames, a próxima chamada
pública reaproveita o journal sob o lease, valida a geração anterior e a
restaura; o staging válido permanece retomável. `inspect()` classifica o caso
como `stable`, `recoverable`, `incomplete` ou `writer_busy`, sem expor caminho
privado, corpus ou traceback. Um owner local comprovadamente morto pode ser
reclamado imediatamente; locks de host remoto conservam a janela stale.

`rag/index.json` usa métricas nomeadas: `corpus_documents` é a quantidade
de documentos aceitos pelo operador, `operator_chunks` é a estimativa de
chunks calculada antes do backend e `backend_total_chunks`/
`backend_total_documents` são estatísticas devolvidas pelo RAGFlow (ou `null`
quando o RAG não foi executado). Não há um alias `chunks` na geração
nova, portanto valores diferentes não podem ser confundidos.

## Limites deliberados

OCR real está disponível no perfil fixado em Docling/RapidOCR e registra páginas,
bounding boxes e confiança. Browser rendering, autenticação de fonte e
confirmação de licença continuam gates explícitos. O manifesto retorna um
código de ação (`browser`, `authentication_required` ou `license_required`)
quando o harness precisa de uma capacidade externa ainda não autorizada.
