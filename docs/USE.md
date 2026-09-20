# Uso operacional

Este é o guia curto do piloto/produto. O contrato completo está em
[ARCHITECTURE.md](ARCHITECTURE.md), e o passo a passo por harness em
[HARNESSES.md](HARNESSES.md).

## Instalação

```text
python scripts/bootstrap.py --dev
python -m docops doctor --json
python -m pytest
```

Para o MCP local:

```text
python scripts/bootstrap.py --dev --rag
python scripts/run_release_gates.py --profile ragflow --json
```

No Windows use `scripts/bootstrap.ps1`; em Linux/macOS use
`sh scripts/bootstrap.sh`. `doctor` trata o RAG como capacidade opcional;
`DOCOPS_REQUIRE_RAG=1 python -m docops doctor --json` torna-o obrigatório.
Se o mesmo checkout for acessado por Windows e WSL, o bootstrap detecta um
`.venv` de outra plataforma e usa `.venv-windows` ou `.venv-posix`, evitando
que um ambiente nativo seja sobrescrito; esses diretórios são ignorados pelo
Git.

## Protocolo único de fonte

```text
python -m docops resolve <nome|URL|repo|pasta> --json
python -m docops plan <nome|URL|repo|pasta> --output <pacote> --license <id> --json
python -m docops run <nome|URL|repo|pasta> --output <pacote> --license <id>
python -m docops validate <pacote> --json
```

`resolve` não baixa nem executa nada. Nomes usam o catálogo oficial e param
quando a confiança é ambígua; uma URL de repositório pode receber `--version`
e `--scope`. Para catálogo próprio, passe `--catalog catalog.json` a `resolve`
ou `run`.

`plan` executa as fases somente leitura, calcula add/update/remove, valida
licença e mostra blockers/readiness esperados. `run` aplica esse plano em
staging; `--mode create` e `--mode update` impõem as invariantes de ciclo de
vida, e `--mode dry-run` é o alias sem efeitos. Uma falha deixa a geração ativa
intacta e pode deixar staging resumível; `inspect()` mostra tentativas e
resíduos sem conteúdo privado e espera um writer vivo terminar a promoção.
`cleanup()` remove apenas resíduos expirados segundo a política de retenção;
ela nunca remove a geração ativa nem staging resumível recente.

O `run` gera skill, router, corpus normalizado, `config.yaml`, `harness.json` e
manifesto. A configuração padrão é relativa ao pacote e não sobrescreve uma
configuração existente. A indexação RAGFlow é uma operação externa opt-in;
sem o perfil autorizado, o `rag/index.json` fica em modo `corpus-ready`.

`rag/index.json` uses named metrics: `corpus_documents` counts documents
accepted by the operator; `operator_chunks` is the local estimate before the
backend; `backend_total_documents` and `backend_total_chunks` are totals
observed from RAGFlow, or `null` when real indexing was not executed.
The current generator does not emit the ambiguous `documents`/`chunks` aliases.

## Atualização e integração externa

O backend legado foi removido. Para verificar a integração externa e o estado do
cutover, use:

```text
python scripts/run_release_gates.py --profile ragflow --json
python scripts/run_cutover_dual.py --json
python -m docops doctor --json
```

O core aplica mudanças por arquivo, salva checkpoint após cada operação e não
inicia serviço externo. Credenciais RAGFlow ficam somente no ambiente do perfil.

`scripts/update_docs.ps1 -Sources <fonte> -Slug <slug>` agora delega ao
`docops run`; não há instrução de copiar/colar no caminho feliz. O
`book-to-skill` instalado no harness pode enriquecer o scaffold estrutural e
validá-lo, mas o operador não cria uma sessão de IA nem envia chaves a um
provedor.

## Configuração e segurança

O `config.yaml` usa caminhos relativos e transporte `stdio`. Não exponha o
servidor na rede sem copiar `config/network.example.yaml` para um arquivo
privado, definir um bearer token forte e executar:

```text
python -m docops config-audit config/network.yaml --json
```

O auditor exige autenticação, rate limit, métricas e logging JSON para `sse` e
`streamable-http`, e o servidor recusa iniciar se o bearer token estiver
ausente. Não coloque esse arquivo no Git. O perfil RAG usa `PersistentClient`
local. O cache de modelos fica fora do pacote, em
`~/.cache/docops/models`; ele é estado de execução e nunca integra o artefato
distribuível.

## Avaliação

```text
python -m docops golden-candidates <pacote> --json
python -m docops evaluate --package <pacote> --cases <golden-revisado.json> --adapter lexical --json
python -m docops evaluate --package <pacote> --cases <golden-revisado.json> --adapter mcp --runtime-root . --json
python -m docops evaluate --package <pacote> --cases <golden-revisado.json> --adapter mcp --response-receipt <evaluation-receipt.json> --json
python -m docops candidate-approve --package <pacote> --candidate-id <id> --actor <identificador-local> --role human_approver --json
python -m docops candidate-publish --package <pacote> --candidate-id <id> --json
python -m docops candidate-rollback --package <pacote> --release-id <release-id> --json
python -m docops source-register --package <pacote> --source-id <id> --canonical <url-ou-caminho> --kind web --scope 'docs/**' --version-policy pinned --version <versao> --rights <licenca> --privacy public --authority official --owner <responsavel> --json
python -m docops source-reconcile --package <pacote> --snapshot <acquisition-snapshot.json> --json
python -m docops source-reconcile --package <pacote> --snapshot <acquisition-snapshot.json> --withdraw --json
python -m docops event-submit --queue <fila.sqlite> --event <event.json> --now <RFC3339> --json
python -m docops jobs --queue <fila.sqlite> --now <RFC3339> --json
python -m docops work --once --queue <fila.sqlite> --now <RFC3339> --json
python -m docops impact-assess --package <pacote> --events <events.json> --json
python -m docops reader-session --package <pacote> --adapter memory --now <RFC3339> --json
python -m docops reader-query --package <pacote> --session <id> --tool search_knowledge --query "..." --adapter memory --now <RFC3339> --json
python -m docops reader-session-revoke --package <pacote> --session <id> --now <RFC3339> --json
python -m docops rag-snapshot --package <pacote> --backend ragflow --supports-incremental --snapshot-out <snapshot.json> --json
python -m docops rag-snapshot --package <pacote> --previous <snapshot.json> --backend ragflow --supports-incremental --verify-query "..." --json
python -m docops rag-profile-compare --package <pacote> --profiles compact,multilingual --language pt-BR --json
python -m docops learning-submit --package <pacote> --proposal <proposal.json> --capture-opt-in --json
python -m docops learning-review --package <pacote> --proposal-id <id> --decision admit --actor <revisor-local> --json
python -m docops learning-review --package <pacote> --proposal-id <id> --decision revoke --actor <revisor-local> --json
python -m docops feedback-submit --package <pacote> --feedback <feedback.json> --json
python -m docops feedback-submit --package <pacote> --feedback <feedback.json> --queue <fila.sqlite> --now <RFC3339> --json
python -m docops feedback-report --package <pacote> --window-days 7 --now <RFC3339> --json
python scripts/run_release_gates.py --profile ragflow --json
```

Os comandos acima são aliases planos de uma hierarquia canônica. Para novos
integradores, prefira `python -m docops lifecycle ...`, por exemplo
`lifecycle reader session`, `lifecycle rag snapshot`, `lifecycle learning
submit`, `lifecycle feedback report` e `lifecycle worker run`; os aliases
continuam emitindo o mesmo envelope e código de saída durante a migração.

O adapter `lexical` é um diagnóstico rápido; `memory` é adequado ao TDD; o
adapter `mcp` é a avaliação híbrida real e exige `rag/index.json` em modo
`indexed`. Todos exigem Golden revisado e o relatório explicita backend,
versão, perfil, corpus, rota, top-k e casos. Um `evaluation-receipt` externo
deve declarar `generation_id`, `candidate_id`, `package_composition_hash`,
`golden_revision`, avaliador independente e julgamentos por caso. O comando
calcula fidelidade e cobertura de citação separadamente; recibo ausente,
inválido ou stale não aprova a candidata. Toda resposta factual do harness
deve citar `path#secao` ou `path:linha`.

`learning-submit` exige `--capture-opt-in` e uma proposta com consentimento
escopado, finalidade, validade e evidência verificável; a proposta permanece
em quarentena até revisão humana. `feedback-submit` recebe um sinal
operacional com `event_id` e uma origem autenticada (`authentication`); redige
a pergunta, preserva somente hashes e métricas mínimas, rejeita replay e aplica
rate limit por origem sem alterar a geração ativa. `feedback-report` consolida
uma janela de uso, deduplica repetições por sessão/pergunta/geração e abre uma
investigação/candidata Golden somente após três ocorrências independentes.
Relatórios incluem latência, custo e denominadores; comparações com dataset ou
geração incompatíveis ficam `not_comparable`, nunca regressão controlada. O
worker de `feedback_report` apenas grava o relatório e o recibo; revisão,
publicação e reindexação continuam gates explícitos.

`rag-snapshot` é somente leitura sobre o pacote ativo: registra hashes e
tamanho do conteúdo, identidade do embedding e um inventário
relocável de `rag/index.json`/`rag/data`. Com `--previous`, compara sempre o
hash do conteúdo, inclusive quando mtime e tamanho não mudaram. Embedding,
artefato lógico do backend ou backend sem capacidade declarada de reuso fazem
o relatório escolher `full_rebuild`; nunca há alegação falsa de incremental.
O relatório traz `active_preserved=true` e `publication_allowed=false`.
`--verify-query` executa uma busca pós-snapshot pelo adapter escolhido para
conferir contagem e fontes; em TDD usa `memory`, enquanto RAGFlow externo exige
o perfil opt-in e não é acionado implicitamente.

Resultados de busca preservam localizadores quando o extrator oferece estrutura:
`page`, `slide`, `sheet`, `cell`, `section`, `timestamp` e `identifier`. Sem um
localizador estável, a resposta usa `normalized_section`, marca
`available=false` e declara a limitação; o sistema não inventa página, aba ou
timestamp. `.vtt`, `.srt`, `.ass` e `.ssa` não são tratados como transcrição
nativa: forneça Markdown externo com timestamps para indexação auditável.

Extrações com texto ausente, caracteres de substituição ou excesso de controles
ficam em `quarantined`, não geram conteúdo em `rag/` e tornam o manifesto
`partial`. O diagnóstico `rag-profile-compare` é somente leitura: ele compara
perfis, mas não altera a configuração nem indexa. A seleção final exige avaliação
Golden nativa em português; qualquer mudança de perfil exige `full_rebuild`
antes de promoção.

Uma candidata só pode avançar com `candidate-approve` e depois
`candidate-publish`. O primeiro grava um recibo de aprovação com a base,
composição, política, avaliação e revisões exatas; o segundo revalida tudo sob
lease, promove com journal e valida o pacote publicado. `approved=true` dentro
de conteúdo não tem autoridade. No piloto, `human_approver` representa uma
decisão explícita do operador local; `delegated_policy` é reservado à política
factual determinística e não equivale a aprovação conceitual humana. A
identidade local não é autenticação remota.

Uma sessão criada por `reader-session` fixa o `release_id` e o
`composition_hash` da composição consultada. `reader-query` aceita somente
`search_knowledge` e `get_document`; ferramentas de escrita, desconhecidas ou
de manutenção são recusadas pelo backend. O cache inclui sessão e geração, e
`reader-session-revoke` invalida consultas futuras sem alterar o pacote.

O adapter `mcp` só é aceito quando `harness.json` declara explicitamente
`mode=read_only`, as duas capacidades de leitura, nenhuma capacidade de escrita
e `concurrent_publication_allowed=false`. Sessões, cache e revogações ficam no
diretório runtime irmão `.<nome-do-pacote>.readers/`, fora da composição ativa e
ignorado pelo Git. Uma sessão antiga só continua disponível enquanto a geração
retida existir no histórico e não estiver revogada; um pacote substituído
diretamente sem histórico torna a geração indisponível.

Após uma publicação, a geração anterior é retida em um diretório editorial
irmão do pacote (`.<nome>.history/`), separado de staging, backups e tentativas
operacionais. `inspect()` lista os releases retidos e `candidate-rollback`
valida recibo, composição, índice e pacote inteiro antes de promover uma cópia
com journal. Gerações revogadas ou marcadas como incompatíveis com o índice são
recusadas sem alterar a ativa. `cleanup()` não remove o histórico editorial.
Quando configurada, a quota de retenção pode ser limitada por
`DOCOPS_HISTORY_QUOTA_BYTES`; publicação nova falha antes da promoção se a
retenção necessária exceder essa quota.

O registro de fontes fica em `.docops/source-registry.json`. `source-register`
adiciona ou atualiza uma identidade explícita por `source_id` e preserva outras
fontes, mesmo quando o canonical é fisicamente igual. Cada
`source-reconcile` exige um `acquisition-snapshot` com escopo e completude:
snapshots parciais, falhos, limitados por robots ou por orçamento são registrados
como observações preservadas e nunca viram tombstone. Uma versão `pinned` não
avança a partir de uma observação nova. Snapshot completo vazio exige
`--withdraw` explícito; sem essa autorização o comando falha fechado e mantém a
fonte ativa. O planejamento também não anuncia remoções depois de uma aquisição
vazia ou incompleta.

A coordenação local aceita envelopes `event` e expõe jobs pela CLI, sem exigir
inspeção da tabela SQLite. O mesmo `event_id` com o mesmo payload é
idempotente; o mesmo identificador com payload divergente falha fechado. Eventos
da mesma chave de trabalho usam `due_at = min(last_event + 60s, first_event +
5min)`. O payload pode indicar `completed_files`/`stable_files` e
`deferred_files`/`unstable_files`; arquivos adiados não bloqueiam os concluídos.
`work --once` adquire um lease curto, executa no máximo um job e reconhece apenas
efeitos comprovados. A execução automática aceita somente
`publication_policy=candidate`; `candidate-publish` continua sendo o gate
explícito. Para `index_rag=true`, o pacote precisa conter
`.docops/rag-authorization.json` com `package_id`, `target_revision` e
`policy_revision` exatos. Um recibo em `.docops/job-receipts/` permite retomar
após crash sem repetir a candidata ou outro efeito já aplicado. Falhas
transitórias fazem retry limitado; falhas de política ficam `blocked`.
Eventos recebidos durante um job `running` formam o lote seguinte. A fila é
estado operacional e deve ficar fora da árvore ativa; aquisição ignora
`.docops` e o Git ignora `.docops/*.sqlite*`.

`impact-assess` mantém um cursor por identidade de documento e revisão. Reindex
sem diferença documental não cria lote; uma reversão à revisão-base remove o
documento do contador; impacto factual fica fora do lote conceitual. O limite
padrão é dez documentos, ou pelo menos três e 10% do corpus, e o orçamento de
lotes é limitado a quatro em 24 horas. Impacto incerto produz
`review_required`, nunca autorização de publicação. Quando o orçamento acaba,
o lote fica visível em `backlog`; revogações invalidam o suporte imediatamente e
não consomem orçamento.

O suporte publicado é Python 3.11–3.13 em Ubuntu, Windows e macOS; Python 3.14
é somente tolerado localmente. A matriz normativa está em
`docs/SUPPORT-MATRIX.json` e é validada por `scripts/check_support_matrix.py`.

## Auditoria de dependências

Em cada release, execute no ambiente usado pelo RAG:

```text
python scripts/audit_dependencies.py --requirements requirements.lock --local --strict
```

O comando falha para qualquer advisory. Trocar o perfil de embedding exige
rebuild completo e receipt novo; não reutilize um índice com dimensão ou modelo
diferentes.
Para integração Python, use a interface raiz documentada em
[`docs/PYTHON-API.md`](PYTHON-API.md); `docops.pipeline` permanece somente como
adapter de compatibilidade.
