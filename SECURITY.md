# Segurança

## Como reportar

Use o fluxo privado de vulnerabilidade do GitHub na aba **Security** ou em
[Report a vulnerability](https://github.com/VIDORETTO/farol-rag-skill-docs/security/advisories/new).
Não abra uma issue pública para uma falha ainda explorável. Inclua a versão ou
commit afetado, sistema operacional, comando reproduzível, impacto e um fixture
mínimo sanitizado. Nunca anexe corpus privado, índices, tokens, credenciais ou
logs que os contenham.

O formulário privado, secret scanning, push protection e Dependabot devem ser
verificados autenticado pelo mantenedor antes de cada release. Uma leitura
pública não prova o estado dessas configurações.

## Escopo e versões

O escopo inclui o código Python em `docops/`, scripts, workflows, configuração
de release, templates, schemas, os perfis opcionais e a integração externa
RAGFlow. O pacote público continua com o identificador técnico
`consulta-documentacao`. A release estável `v1.1.0` permanece disponível para
compatibilidade; `v2.0.0-rc.1` é a prévia atual da superfície Farol 2.0 e não
deve ser tratada como contrato final.

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
| Processos locais | limpeza atinge somente o PID exato criado pelo projeto; nenhum comando global encerra Python | leitores de filesystem podem observar janelas específicas de troca de diretório |

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
