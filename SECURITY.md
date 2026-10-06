# Segurança

## Como reportar

O fluxo privado de vulnerabilidade do GitHub está habilitado neste repositório;
o estado foi confirmado por API autenticada em 2026-09-25. Use a aba
**Security** ou [Report a vulnerability](https://github.com/VIDORETTO/farol-rag-skill-docs/security/advisories/new)
para comunicar problemas de forma privada. Se o formulário não estiver
disponível, não publique detalhes exploráveis em uma issue; confirme a
configuração com um mantenedor.
Inclua versão ou commit afetado, sistema operacional, comando reproduzível,
impacto e um fixture mínimo sanitizado. Nunca anexe corpus privado, índices,
tokens, credenciais ou logs que os contenham.

O formulário privado, secret scanning, push protection e Dependabot devem ser
verificados autenticado pelo mantenedor antes de cada release. Uma leitura
pública não prova o estado dessas configurações.

## Escopo e versões

| Versão | Suporte de segurança |
|---|---|
| 3.1.x | sim (atual) |
| 3.0.x | sim, até 3.2.0 |
| < 3.0 | não |

O escopo inclui o código Python em `docops/` (distribuição `farol-kit`,
comandos `farol` e `docops`), scripts, workflows, configuração de release,
templates, schemas, os extras opcionais (`semantic`, `media`, `ocr`, `layout`,
`ragflow`) e a integração externa RAGFlow.

Corpus, índices, caches, ambientes virtuais, tokens, credenciais, artefatos de
execução e arquivos em `config/network.yaml` são dados locais e não fazem parte
do release. A versão 2.0 não distribui `knowledge-rag`, `chromadb` nem um
backend legado vendorizado.

Ficam fora do escopo falhas que exigem controle prévio do checkout, acesso ao
sistema de arquivos do operador ou um modelo/LLM escolhido pelo usuário, salvo
quando o impacto atravessar uma fronteira controlada pelo produto.

## Modelo de ameaça e controles

| Fronteira | Controle aplicado | Limitação conhecida |
|---|---|---|
| URL e crawler | bloqueio de credenciais, loopback, metadata cloud e redes privadas; revalidação de redirects; limites de host, páginas, profundidade, payload, timeout e retries | não é um sandbox para sites hostis nem um navegador JavaScript |
| Repositório Git | somente HTTPS remoto; políticas de DNS/redirect, sem submódulos, protocolo `file`, prompt interativo ou tags desnecessárias; limites pós-clone | não há quota de bytes garantida antes de o servidor iniciar a transferência |
| Documentos e OCR | conteúdo tratado como dado não confiável; extractors produzem IR canônica, locators e quarentena; Docling/RapidOCR é opt-in | autenticação da fonte, browser rendering e licença continuam capacidades externas |
| IR e proveniência | identidade canônica separada de IDs do backend; hashes, lineage, locators e receipts verificáveis | um locator inexistente ou uma fonte sem direitos deve bloquear a promoção |
| MCP local | `stdio` é o padrão; HTTP/SSE é opt-in e exige bearer token, rate limit, métricas e logging JSON | quem altera o bind para uma rede deve aplicar firewall e TLS/proxy adequados |
| RAGFlow externo | endpoint e token fora do pacote; SDK `0.27.2`; imagem fixada por digest; HTTPS remoto e loopback explícito no desenvolvimento | o projeto não gerencia rotação de token, cofre de segredos ou identidade multiusuário |
| Artefatos e publicação | originais privados, caches e credenciais são excluídos; candidate, wheel, supply-chain e clean clone são auditados | licença da fonte e autorização de publicação continuam decisão humana |
| Vídeos, playlists e cursos | YouTube só por `yt-dlp` (extra `media`), apenas legendas/metadados; IDs de playlist validados por regex; licença registrada por vídeo e redistribuição forçada para `private-only` quando algum vídeo não é Creative Commons; pasta de curso local exige licença declarada | termos de plataformas e cookies (`FAROL_YTDLP_COOKIES`) são responsabilidade do usuário |
| Slides de vídeo (`--slides`) | `ffmpeg` chamado com lista de argumentos (sem shell), saída em diretório temporário; OCR local | só texto é extraído; o vídeo é tratado como entrada não confiável pelo próprio `ffmpeg` |
| `farol connect` | grava só nos caminhos do harness; `--remove` restaura configurações byte a byte; ao reconectar, só remove arquivos regulares dentro da pasta de skills do harness, mesmo que `.farol/connect.json` seja adulterado | configurações de terceiros editadas manualmente perdem só a entrada `farol` |
| Síntese pelo agente | blocos `high` nunca chegam às tarefas; respostas validadas (citações, cópia, injeção); plano protegido por lock contra perda de atualização com agentes paralelos; o MCP continua somente leitura (D-303) | a qualidade da skill depende do modelo do usuário |
| Camada de síntese e `get_context`/`get_document` | blocos `high` nunca são devolvidos; afirmações da skill vêm com os blocos de suporte e a orientação de citar só os blocos | uma afirmação parafraseada pode simplificar a fonte; o agente deve conferir os `supports` |
| Processos locais | limpeza atinge somente o PID exato criado pelo projeto; nenhum comando global encerra Python | leitores de filesystem podem observar janelas específicas de troca de diretório |

## Conteúdo hostil e prompt injection

Fontes são dados, nunca instruções. O módulo `docops/safety.py` classifica cada
bloco em `none`, `suspicious` ou `high`:

- `high` — diretiva dirigida à IA leitora (ignorar instruções anteriores, assumir
  outro papel, revelar segredos, enviar dados para URL, invocar ferramentas).
  Esses blocos nunca são devolvidos pelo MCP nem aceitos em skills; um documento
  dominado por eles (≥ 25% dos parágrafos) vai inteiro para quarentena.
- `suspicious` — texto legítimo no contexto, mas parecido com prompt ou com
  caracteres invisíveis/bidi/Unicode tags; é devolvido marcado com `risk`.

Toda resposta do MCP com evidência inclui a nota de conteúdo não confiável.
Limites: é uma camada determinística por padrões, testada contra um corpus
adversarial rotulado (`tests/fixtures/adversarial/`) e medida contra falsos
positivos no corpus real; não substitui a política do harness nem garante
detecção de ataques novos, ofuscados ou em idiomas não cobertos.

## Transporte e credenciais

O arquivo `config.yaml` usa caminhos relativos e transporte `stdio`. Para testar
um transporte HTTP/SSE, copie `config/network.example.yaml` para um arquivo
privado, substitua o placeholder do bearer token e execute:

```text
python -m docops config-audit config/network.yaml --json
```

O RAGFlow não deve ser exposto publicamente sem autenticação, HTTPS, logs
redigidos e autorização operacional. `DOCOPS_RAGFLOW_TOKEN`, endpoints e
digests de imagem nunca entram no Git.

## Gates antes de publicar

```text
python -m docops doctor --json
python -m pip check
python -m pip_audit --requirement requirements.lock --format json
python scripts/audit_dependencies.py --requirements requirements.lock --local --strict
python scripts/check_contracts.py --json
python scripts/check_documentation.py --json
python scripts/verify_clean_clone.py
python scripts/run_release_gates.py --profile full --timeout 3600 --json
```

O perfil RAGFlow somente pode ser considerado aprovado com endpoint, token, SDK,
imagem por digest e receipt real. Ausência de qualquer input é `blocked` ou
`not_run`, nunca sucesso.

## Limitações e resposta a incidentes

Browser rendering, autenticação de fonte, confirmação de licença e autorização
comercial não são inferidos pelo operador. O manifesto conserva códigos de ação
e o harness autorizado decide como prosseguir.

Ao confirmar uma falha, preserve evidências sem redistribuir dados protegidos,
revogue tokens afetados, bloqueie o vetor no código/configuração, publique uma
correção ou orientação de mitigação e só então divulgue detalhes suficientes
para usuários atualizarem com segurança.

As referências históricas a Chroma e ao piloto FastAPI permanecem em auditorias
arquivadas para explicar decisões anteriores; elas não são a política de
segurança do artefato Farol 2.0.
