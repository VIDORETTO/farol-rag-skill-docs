# Instalar e começar a usar o Farol

O Farol transforma documentação, livros, papers, vídeos e repositórios em
**skills** (escritas pela sua própria IA, com citações) e **evidência citada**
servida por MCP. Tudo roda localmente: sem conta, chave de API ou Docker.

## 1. Instalar

Requer Python 3.11–3.13 (Windows, Linux ou macOS). Com
[pipx](https://pipx.pypa.io/) ou [uv](https://docs.astral.sh/uv/):

```bash
pipx install "farol-kit[semantic] @ git+https://github.com/VIDORETTO/farol-rag-skill-docs@v3.1.0"
```

```bash
uv tool install "farol-kit[semantic] @ git+https://github.com/VIDORETTO/farol-rag-skill-docs"
```

Confira a instalação:

```text
farol doctor
```

| Extra | Para quê | Custo |
| --- | --- | --- |
| `formats` (sempre incluído) | PDF, DOCX, EPUB, YAML | pequeno |
| `semantic` (recomendado) | busca híbrida multilíngue, perguntas em PT sobre fontes em EN | ~220 MB de modelo, baixado no primeiro uso |
| `media` | YouTube e reconhecimento de fala local (áudio/vídeo) | modelos de fala baixados no primeiro uso |
| `ocr` | PDFs escaneados (Python 3.13) | grande |
| `layout` | PDFs digitais com títulos e tabelas preservados (Python 3.13); ative com `FAROL_PDF_LAYOUT=1` | grande |
| `ragflow` | usar um servidor RAGFlow externo como backend (Python 3.13) | serviço próprio |

Combine extras separando por vírgula: `farol-kit[semantic,media]`.

## 2. Criar um projeto e adicionar fontes

Um projeto é uma pasta com `farol.json`. Cada fonte vira um pacote com a sua
própria skill.

```bash
mkdir meu-conhecimento && cd meu-conhecimento
farol add ./docs-da-minha-api --license MIT
farol add https://www.python-httpx.org --license BSD-3-Clause
farol add arXiv:2404.16130v2
farol add ./aula.mp3 --license CC-BY-4.0
farol build
```

Informe a licença real de cada fonte. Sem licença, o Farol trata o pacote como
de uso local e privado e avisa em `farol status`. Para arXiv e YouTube, a licença
declarada na página é detectada automaticamente.

### Cursos

Um curso é **uma** fonte: `farol add ./curso --as course --license <licença>`
(pasta de aulas em vídeo, áudio, legendas, PDF ou Markdown; subpastas viram
módulos e a ordem é a natural: “Aula 2” antes de “Aula 10”) ou
`farol add "https://www.youtube.com/playlist?list=…" --as course` (legendas de
cada vídeo na ordem da playlist, licença conferida por vídeo; `--max-items`
limita a quantidade). As citações nomeiam a aula e o momento `(at HH:MM:SS)`.
Em videoaulas locais, `--slides` também lê o texto mostrado nos slides
(requer `ffmpeg` e o extra `ocr`); imagens e diagramas não são interpretados.

### Uma skill sobre várias fontes

Vários livros, cursos ou sites sobre o mesmo assunto podem formar **uma** skill
temática: `farol skill compose python --from livro-python curso-python`. As
tarefas citam blocos de todas as fontes, a busca continua em cada uma e o
`farol sync` de qualquer fonte reabre só os capítulos afetados. Adicione as
fontes com `--no-skill` para não escrever também uma skill por fonte.

## 3. Deixar a sua IA escrever as skills

`farol build` deixa as fontes consultáveis e prepara tarefas de síntese. Depois
de `farol connect`, o agente já tem a skill `farol-distill`, que conduz todo o
ciclo; basta pedir “escreva as skills do Farol”. Sem ela, peça ao seu agente
(Claude Code, Codex, Cursor, OpenCode…):

> Rode `farol task next` em `~/meu-conhecimento`, faça a tarefa, envie com
> `farol task submit` e repita até não haver mais tarefas.

Para fontes grandes, a primeira tarefa é o sumário (`outline`): o agente agrupa
as seções em capítulos por assunto. Cada resposta é validada — seções,
citações `[b12]`, orçamento de tokens, cópia literal e instruções maliciosas — e
rejeições explicam o que corrigir. Acompanhe com `farol status`.

Em agentes com subagentes (por exemplo Claude Code), os capítulos podem ser
feitos em paralelo: `farol task claim --n 4` reserva quatro tarefas, cada uma
com um lease que expira (`--ttl`, padrão 30 min); cada subagente envia a sua com
`farol task submit <id> <pasta> --lease <lease_id>`. Nenhum outro agente recebe
uma tarefa reservada enquanto o lease vale, e envios simultâneos não se perdem.

### Medir a qualidade do seu pacote

`farol eval` pesquisa cada afirmação da skill destilada e confere se os blocos
que ela cita voltam no top 5 (recall@5 e MRR@5, pior capítulo primeiro). É uma
autoavaliação otimista; para algo mais próximo do uso real, peça perguntas ao
agente com `farol task plan --questions 3` e rode `farol eval` de novo.

## 4. Conectar ao seu agente

```bash
farol connect claude-code --target ~/meu-repositorio
```

| Agente | O que é configurado | Observação |
| --- | --- | --- |
| `claude-code` | `.mcp.json` e `.claude/skills/` | aprove o servidor `farol` ao abrir o Claude Code |
| `codex` | `.codex/config.toml` e `.agents/skills/` | projeto precisa ser confiável no Codex |
| `cursor` | `.cursor/mcp.json` e `.cursor/rules/farol.mdc` | habilite o servidor nas configurações |
| `opencode` | `opencode.json` e `.opencode/skills/` | reinicie o OpenCode |
| `generic` | imprime a configuração MCP | para outros clientes MCP |

Use `--dry-run` para ver as mudanças antes, `--scope user` para configurar o seu
usuário em vez de um repositório e `--remove` para desfazer (arquivos que você
não editou voltam exatamente ao original).

## 5. Manter atualizado

```bash
farol sync
```

`sync` atualiza os fatos, informa o que mudou e marca como `stale` apenas os
capítulos cuja evidência citada mudou; `farol task plan --refresh` reabre só
esses capítulos. Para rodar todo dia, `farol sync --schedule cron` (ou
`systemd`, `windows`) imprime a configuração exata para você instalar.

## Resolver problemas

Todo erro mostra um código e o próximo passo; a lista completa está na
[referência de erros](ERRORS.md). Os mais comuns:

| Sintoma | Próximo passo |
| --- | --- |
| `project_missing` | Rode `farol add <fonte>` na pasta do projeto. |
| `nothing_to_connect` | Rode `farol build` antes de `farol connect`. |
| `youtube_blocked` | Exporte cookies do navegador para um arquivo e defina `FAROL_YTDLP_COOKIES`, ou adicione o `.vtt`/áudio baixado. |
| `asr_unavailable` / `extra_required` | Instale o extra `media`. |
| `index_unreadable` | `farol doctor --fix` reconstrói o índice. |
| Busca responde pouco em PT sobre fontes em EN | Instale o extra `semantic` e rode `farol build`. |

## Opcional: reranker local

Com o extra `semantic`, um cross-encoder local pode reordenar os candidatos
antes do corte `top_k` (projeto e biblioteca). É opt-in e não exige rebuild:

```bash
export FAROL_RERANKER=BAAI/bge-reranker-base   # MIT, ~1 GB
```

O resultado de `search_knowledge` passa a informar
`retrieval_mode: rerank:<modelo>`; se o modelo não carregar, a busca continua
com a ordem do índice e informa `degraded`. `farol doctor --json` mostra o
reranker ativo e a licença. Modelos não comerciais (por exemplo
`jinaai/jina-reranker-v2-base-multilingual`, CC-BY-NC) funcionam, mas a
licença é sua responsabilidade.

## Opcional: RAGFlow como backend

O backend padrão é local. Para usar uma instância
[RAGFlow](https://github.com/infiniflow/ragflow) 0.27.2 própria (Python 3.13,
extra `ragflow`), configure na sessão `DOCOPS_RAGFLOW_ENDPOINT` (HTTPS),
`DOCOPS_RAGFLOW_TOKEN` (sua chave, nunca em arquivo versionado),
`DOCOPS_RAGFLOW_IMAGE_DIGEST` (imagem fixada por `sha256`) e
`DOCOPS_RAGFLOW_SDK_VERSION=0.27.2`, e confira com:

```text
farol doctor --require-ragflow --json
```

Para hospedar localmente, veja o [ambiente Docker fixado](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/main/config/ragflow/README.md).
Mudar o modelo de embedding exige reconstruir o índice.

## Desenvolver a partir do código

```text
python scripts/bootstrap.py --dev
```

O bootstrap cria o ambiente virtual e instala as ferramentas de teste. Veja
[CONTRIBUTING.md](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/main/CONTRIBUTING.md) para o fluxo TDD e as verificações.

## Atualizar e remover

Atualize com `pipx upgrade farol-kit` (ou reinstale com os mesmos extras) e rode
`farol doctor`. Para remover, `pipx uninstall farol-kit`: seus projetos, pacotes
e fontes não são apagados. Os modelos baixados ficam em `~/.cache/farol` e podem
ser removidos manualmente. Para suporte, informe versão, sistema, comando e
saída redigida conforme a [política de suporte](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/main/community/SUPPORT.md).
