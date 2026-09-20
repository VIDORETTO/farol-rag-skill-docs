# Lessons

## 2026-09-13 — oráculo de docs precisa enxergar as cercas reais

- `check_documentation.py` só reconhecia blocos cercados por crase tripla, mas
  o README usa crase: blocos `~~~` ficavam fora do gate. Corrija o scanner para
  aceitar ` ` ` e `~` (mínimo de três) e valide também a notação de grupo
  `docops <grupo> {a,b}` expandindo para comandos concretos.
- Um gate verde que não lê o arquivo onde a prosa contradiz o produto não é
  evidência: confira que a superfície validada é a mesma que o humano lê.
- O gate também ignorava `specs/` (48 Markdown normativos: spec/plan, tickets,
  evidências) — a árvore que carrega as citações verificáveis do projeto. Um
  oráculo precisa cobrir a fonte normativa, não só `docs/`/`README.md`.

## 2026-09-13 — auditor de superfície e wheel contaminado por `build/`

- Um scanner que varre `rglob("*")` do checkout mede o que está no disco, não o
  que é versionado: ele contou ~15k findings de `documents/`, `.venv`,
  `artifacts` e caches. Enumere a superfície normativa a partir de
  `git ls-files` e filtre por prefixo de pacote.
- Padrões de contração devem casar símbolos do contrato, não palavras inglesas
  genéricas: `\bpage\b` acusava o locator legítimo `page` da IR. Ancore em
  `course_id`/`page_id`, `*.schema.json`, `offer.json`, `page.offer` etc.
- O wheel 1.1.0 continuou trazendo `course.schema.json`, `page.schema.json` e
  `presets/mercado-livre.json` depois de removê-los do checkout, porque o
  `build/lib` gitignored ainda os continha e o setuptools copiou de lá. Antes
  de usar o wheel como oráculo de aceite, limpe artefatos de build obsoletos e
  reconstrua.
- Deleções só entram no índice após `git rm`/`git add`: `git ls-files --cached`
  segue listando arquivos apenas apagados do disco, o que faz verificadores de
  candidato verem “missing file” até o índice ser atualizado.

## 2026-09-13 — denominadores de gate precisam ser idempotentes

- O agregado do `run_release_gates.py` re-somava as etapas anteriores a cada
  atualização, inflando o resultado para `7419 passed / 150 skipped`. O número
  real do candidate é `1077 passed / 20 skipped` (`22` créditos de etapa mais
  `1055` testes; skips são as duas execuções de suíte com `10` cada). Agregados
  de gate devem ser calculados de forma idempotente e ter semântica explícita.
- Contagens de suíte dependem do ambiente: o core isolado (Python 3.11, sem
  `chromadb`) registra `499 passed, 10 skipped`, enquanto o venv do projeto
  (Python 3.14.2, com `chromadb`) registra `504 passed, 5 skipped`. Registre o
  ambiente junto da contagem e não atribua números históricos ao candidate
  atual sem um relatório terminal próprio.

## 2026-09-12 — não usar `rtk`

- O usuário corrigiu explicitamente o workflow: comandos shell devem ser
  executados sem o wrapper `rtk`. Não invocar `rtk` em nenhuma etapa futura;
  preservar apenas a redaction e os limites de saída necessários diretamente
  no comando usado.

## 2026-09-04 — prontidão, publicação e divulgação são gates diferentes

- Um candidate técnico verde não é uma release pública: commit, digest, CI,
  tag, registry, canário e anúncio precisam apontar para a mesma identidade.
- “Sem intervenção” pode eliminar perguntas intermediárias, mas não substitui
  decisão humana de risco, licença, ownership, credenciais ou autorização de
  publicação.
- Para um pacote/CLI/MCP, produção é distribuição verificável; não inventar um
  deploy de serviço, VPS ou banco quando o produto não os possui.
- Divulgação em massa deve esperar uma publicação controlada e uma janela de
  observação; rollback deve preservar a tag e gerar uma nova versão.

## 2026-08-29 — confirmar o repositório antes de continuar

- Antes de implementar, fazer uma verificação explícita de `cwd`, `origin`, branch e projeto declarado no README/handoff.
- Se houver mais de um checkout relacionado, não tratar o handoff de um repositório como autorização para alterar outro.
- Antes de publicar, conferir o commit remoto, o workflow do próprio repositório e a página GitHub que o usuário está visualizando.

## 2026-09-03 — probes determinísticos em Windows e gates reais

- Nunca use o resultado de um clean clone iniciado antes da última correção;
  reexecute o clone e os gates depois de fechar o snapshot do candidato.
- No Windows, trate o PID do próprio processo como vivo antes de consultar
  `os.kill`; erros Win32 podem ser ambíguos e provocar recuperação indevida do
  próprio lease.
- Exclua estado local ignorado ao copiar o clean clone/candidato e ordene a
  lista de arquivos em POSIX; o worktree e o clone sem `.git` precisam medir o
  mesmo conteúdo distribuível.
- Preserve o resultado cru do `pip-audit` separado da allowlist; um wrapper
  estrito com residual aceito não deve ser descrito como auditoria limpa.
- Para gates longos, use processo destacado com logs e valide o PID/comando
  antes de iniciar uma nova execução.

## 2026-09-04 — identidade sem referência circular

- Nunca copie o digest do candidate de volta para um arquivo que participa do
  conjunto medido; a documentação precisa apontar para o manifest do bundle,
  sem se auto-referenciar.
- Se uma ferramenta externa falhar antes de produzir JSON (por exemplo,
  resolução de requirements no Python tolerado), preserve a falha como
  evidência de gate vermelho e não a classifique como auditoria limpa.

## 2026-09-04 — evidência CI persistente e redigida

- Um workflow que executa um gate mas descarta seu output não deixa evidência
  auditável; o job deve reter o candidate com nome vinculado a
  `${{ github.sha }}` e falhar se o artefato não existir.
- Resultados de integração devem usar uma lista explícita de arquivos seguros;
  nunca fazer upload do diretório RAG inteiro, que pode conter banco, cache de
  modelo ou dados do corpus.
- O checker da matriz deve verificar esses marcadores no job real, para que a
  retenção não dependa apenas de uma revisão visual do YAML.

## 2026-09-04 — gates devem medir o artefato certo

- Um checker de workflow precisa analisar passos executáveis e paths de
  artefato, ignorando comentários e `if: false`; a presença textual de um nome
  de gate não prova execução nem retenção segura.
- Consultas são dados sensíveis mesmo sem token. Relatórios de doctor, smoke,
  avaliação e stress devem publicar somente códigos, contagens e diagnósticos
  estruturados redigidos.
- A evidência de resolução deve ser o fechamento das raízes do lock, não todo
  pacote incidental instalado no interpretador usado para gerar o candidate.
- Faça a auditoria do snapshot de fonte antes de criar o ambiente dentro do
  clean clone, ou exclua explicitamente apenas o ambiente criado pelo próprio
  gate; caso contrário a verificação acusa o seu próprio bootstrap.
- Em stress concorrente, espere readers ficarem operacionais antes de iniciar o
  writer e não conte o warm-up como carga. Registros terminais bem-sucedidos são
  histórico de auditoria; somente staging, backup ou tentativa recuperável são
  resíduos que reprovam o gate.
- Nunca use `os.kill(pid, 0)` para consultar liveness no Windows: um reader pode
  enviar um evento de console ao writer e interromper o processo correto. Use
  `OpenProcess`/`GetExitCodeProcess` e trate falha de verificação como owner vivo.
  O teste de regressão deve usar um subprocesso real e confirmar que ele continua
  vivo depois da consulta.

## 2026-09-04 — perfis opcionais precisam ser explícitos na evidência

- Um lock agregado pode conter raízes de vários perfis; o verificador não deve
  exigir um componente opcional no core nem ignorar ausências por nome sem
  registrar o perfil medido.
- Separar o perfil de dependências (`core`/`rag`) da exigência de snapshot de
  modelo. Optionalidade permite ausência, nunca aceitar uma versão divergente
  quando o pacote estiver presente.
- Reexecutar o clone limpo completo depois de corrigir gates de candidate; a
  suíte local com RAG instalado pode esconder acoplamentos a dependências
  opcionais.

## 2026-09-04 — caches de runtime não pertencem ao artefato

- Execute pelo menos um smoke RAG em Linux com cache frio: no Windows, a
  ausência de symlinks do snapshot pode ocultar contaminação do pacote.
- Cache de modelo é estado externo de execução. A configuração portátil deve
  apontá-lo para fora da árvore distribuível, sem persistir caminho absoluto
  da máquina.
- Gates que consomem CLIs JSON devem extrair `errors` e `outcome` do documento
  estruturado; truncar apenas o final do stdout pode apagar a causa-raiz.

## 2026-09-04 — smokes de wheel não compartilham estado de build

- Não executar `verify_wheel.py --core` e `--require-rag` em paralelo no mesmo
  checkout: o backend de build usa diretórios `build/` compartilhados e uma
  corrida pode produzir um `WinError 2` que não é falha do produto.
- Distinguir o interpretador global do ambiente RAG do projeto; um gate RAG
  deve apontar para o `.venv` que contém o backend e registrar explicitamente
  `adapter=mcp`, `rag=true`.

## 2026-09-04 — preservar launchers de venv no candidate

- Em POSIX, `bin/python` pode ser symlink para um interpretador de sistema sem
  `pip`; não aplicar `Path.resolve()` ao interpretador selecionado para um
  candidate, pois isso remove o ambiente virtual da invocação.
- Testar construção de candidate em checkout nativo Linux/WSL, não apenas em
  um venv Windows, para cobrir essa diferença de launcher.

## 2026-09-04 — stress RAG deve usar o backend efetivamente revisado

- O harness de concorrência precisa iniciar exatamente a árvore vendorizada
  que o operador usa para indexação e avaliação; passar a raiz do repositório
  como `vendor_root` fez o Python escolher a cópia instalada do PyPI e ocultou
  a diferença de comportamento.
- Durante reindex, o Chroma pode expor transitoriamente uma linha com
  `metadata=None`. O pipeline de busca deve descartar esse hit de forma
  fail-closed: conteúdo sem `source` não é evidência citável e não deve virar
  erro MCP nem resultado vazio.
- Execute testes do vendor a partir do diretório do vendor para que o preset
  de configuração correto seja carregado; executar a partir do monorepo pode
  produzir falhas de configuração que não representam a regressão testada.
- O stress final precisa separar warmups da carga medida e reter somente
  contagens/redações seguras; a evidência remota final observada foi 20.866
  buscas, zero erros/warnings, reindex bem-sucedido e zero resíduo recuperável.
