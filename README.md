# Baltigo Games

Fliperama gratuito para navegador e Telegram Mini App, com 142 jogos, identidade retrô, imagens dos próprios jogos e interface em português brasileiro.

O catálogo oferece busca sem distinção de acentos, categorias, favoritos e histórico por dispositivo, tutoriais por jogo, controles por toque, pausa real, orientação por jogo e classificação geral. Os jogos seguem gratuitos, sem limite de vidas. **Versus, vidas, loja e pagamentos são a próxima etapa; não estão ativos.**

## Executar

```sh
python -m pip install -r requirements.txt
python scripts/sync_upstream.py --help
```

Baixe a versão fixada da fonte dos jogos com `sync_upstream.py` e defina o diretório resultante como `UPSTREAM_LOCAL_DIR`. O comando mostra as opções de destino e versão. Na instalação VPS, o mirror está em `/opt/baltigogames/upstream/c97ef8b`.

```env
APP_URL=https://games.seudominio.com
UPSTREAM_LOCAL_DIR=/caminho/do/mirror
DATABASE_PATH=/caminho/privado/leaderboard.sqlite
BOT_TOKEN=definido_apenas_no_ambiente_privado
```

```sh
uvicorn app.main:app --port 8190 --workers 1
```

Sem `BOT_TOKEN`, funciona como site de jogos; o ranking autenticado exige Telegram. Nunca iniciar dois processos com o mesmo token de long polling. O ambiente de desenvolvimento não deve usar o token de produção. Railway e Render também são reconhecidos pelas variáveis públicas da plataforma; `APP_URL` tem prioridade.

## Jogos e adaptação

A fonte MIT `sausi-7/games` está fixada em `data/upstream-version.json`, com SHA-256 do arquivo baixado. `scripts/sync_upstream.py` verifica a versão e extrai com validação de caminhos. O mirror e suas imagens não precisam ser enviados ao Git.

- `data/registry.json`: catálogo de origem; `data/catalog-pt.json`: nomes, descrições, regras, controles e orientação revisados por jogo.
- `app/source_repairs.py`: correções pontuais da mecânica e dos caminhos dos assets, sem editar a cópia original do mirror.
- `app/game_runtime.py` e `web/game-runtime.js`: adaptação de resposta, tradução de DOM/canvas/Phaser, tutoriais, pausa, início e resultados.
- `data/word-games-pt.json`: palavras, dicas e dicionário em português; não traduz nomes de variáveis, eventos ou caminhos de arquivos.
- `web/covers/`: capturas WebP dos próprios jogos; `data/cover-focus.json` define o enquadramento de cada capa quando necessário. `web/game-art/`: SVGs originais para fundos provisórios e imagens com texto incorporado, nos caminhos explícitos de `data/asset-replacements.json`.
- `web/vendor/`: versões exatas das bibliotecas dos jogos, com mapa e licenças; fontes locais em `web/fonts/`.

O player mantém a barra de ferramentas fora da área nativa do Telegram. Jogos horizontais têm orientação própria e opção de girar a área da partida; o documento do jogo recebe largura e altura reais de paisagem. O mundo do jogo mantém sua proporção. Xadrez é apresentado como versão casual com regras simplificadas.

O player usa a rota versionada `/play-v3/`; `/play/` e `/play-v2/` permanecem compatíveis. O novo prefixo impede que dispositivos reaproveitem documentos, configurações e scripts antigos do cache HTTP. O mirror local é preferido. Se faltar um arquivo, a rota ainda consulta `UPSTREAM_GAMES_BASE`, por padrão a fonte original. Cookies e credenciais do usuário não são encaminhados ao upstream.

Na VPS, o Nginx entrega diretamente os tipos binários públicos permitidos, usando o mirror e os mapas exatos das artes em português. `scripts/render_nginx_assets.py` confere os mapas contra os metadados. Documentos, configurações e estilos continuam no proxy do aplicativo. Arquivos ausentes seguem para o fallback; `GAME_ASSET_ACCEL=1` permite ao Nginx enviá-los depois da validação da aplicação, exigindo os aliases internos de `deploy/nginx.conf`. Sem a flag, a entrega direta permanece disponível no Docker e no desenvolvimento. Os detalhes de instalação e recuperação estão em `deploy/README.md`.

## Classificação e dados

A classificação mede **participação**, não compara pontuações brutas de jogos diferentes. O servidor concede um ponto por 15 segundos ativos, até 10 pontos por partida e 100 por dia. O cliente informa atividade; isso não equivale a validação antitrapaça da mecânica.

`/api/session` valida a assinatura e a idade do `initData` do Telegram. Sessões possuem token opaco, expiram e mantêm isolamento entre usuários. Há limite de requisições, apenas uma partida ativa, finalização idempotente e validação de pontuação não finita. Pontuação local do jogo é apenas diagnóstico e não concede pontos diretamente.

SQLite em modo WAL guarda os dados do ranking em `DATABASE_PATH`. Favoritos e histórico continuam no armazenamento local do dispositivo. Não expor o banco por HTTP. Para backup consistente, usar a API `sqlite3.Connection.backup()`; copiar somente o arquivo principal durante uso pode perder dados do WAL.

## Jogos mais jogados

O Top 10 da página inicial usa `GET /api/games/popular?limit=10`. A contagem geral inclui somente partidas finalizadas de usuários autenticados, com pelo menos 15 segundos de atividade registrada e motivo `registrada` ou `limite_diario`. Sair após jogar também conta; simples aberturas, partidas expiradas e pontuações informadas pelo navegador não influenciam a ordem. Empates usam o identificador do jogo em ordem alfabética.

A resposta pública contém apenas jogos e contagens agregadas, sem dados de jogadores. O servidor mantém um retrato por 60 segundos, com leitura independente da fila de gravação. A lista mostra até dez jogos: quando há menos registros, não cria posições nem partidas fictícias.

## Verificação

```sh
python -m pip install -r requirements-dev.txt
python -m playwright install chromium firefox webkit
python scripts/validate_catalog.py
pytest -q
python tests/e2e_portal.py
python tests/e2e_popular_games.py
python tests/e2e_inline_launch.py
python scripts/audit_games.py --base http://127.0.0.1:8190 --profiles preferred,desktop --covers --workers 2 --output artifacts/qualification-preferred
python scripts/audit_round_transitions.py --base http://127.0.0.1:8190 --phaser-only --workers 2 --out artifacts/terminal-rounds
python tests/e2e_native_rounds.py
python tests/e2e_native_football_hex.py --base http://127.0.0.1:8190
python tests/e2e_authored_campaigns.py --base http://127.0.0.1:8190
python tests/e2e_authored_remaining_campaigns.py --base http://127.0.0.1:8190
python tests/touch_control_audit.py
python scripts/prove_scoped_hud_release.py --base http://127.0.0.1:8190 --out artifacts/hud-release
python scripts/prove_scoped_native_release.py --base http://127.0.0.1:8190 --out artifacts/native-release
python tests/e2e_rotated_gameplay.py --base http://127.0.0.1:8190 --out artifacts/rotated-gameplay
```

`TEST_BASE_URL` seleciona o endereço usado pelos testes do portal. `tests/e2e_smoke.py` e `tests/e2e_matrix.py` são entradas compatíveis para a mesma suíte do portal. `tests/e2e_gameplay.py` executa o auditor completo, por padrão em orientação preferida e desktop.

O auditor abre **cada jogo**, inicia a partida por eventos reais de navegador quando há botão inicial, envia controles de teclado/toque, confere avanço do motor, erros JavaScript, respostas HTTP, menus presos, controles com textura ausente, transbordamento e candidatos de texto em inglês. Retém JSON e imagem de cada caso. Há limite de tempo por jogo; uma página travada falha explicitamente.

O auditor de entrada verifica início e uma sequência curta de comandos. A verificação de transições cobre separadamente os 120 jogos Phaser de rodada única, dois jogos de canvas próprio, 13 fluxos nativos e sete campanhas. Os testes de resultados acionam funções reais do jogo com estado de teste próximo da vitória e usam gestos reais nos botões; isso não equivale a um jogador concluir integralmente todas as fases. As campanhas verificam a progressão que existe no código; uma rodada única não é apresentada como uma fase inédita.

O ensaio de transições exige a versão do runtime na abertura e depois de cada confirmação. Retém o estado do motor, documento, pausa, resultado e novo início. `scripts/collect_qualification.py` reúne os casos de entrada e substituições pontuais, conservando as evidências que falharam. Não usar apenas HTTP 200, um menu aberto ou uma contagem de quadros como prova de uma campanha funcional.

Os testes do portal simulam o cliente Telegram e a autenticação em banco isolado; não substituem teste em celular físico com Telegram aberto. Relatórios e capturas ficam em `artifacts/`, fora do Git.

`tests/e2e_cache_release.py` verifica a atualização de uma sessão com arquivos da versão anterior em cache: mantém a partida aberta, recebe o portal novo e confirma que a próxima abertura usa o prefixo atual também nas dependências relativas. Essa prova usa o cache HTTP real do navegador, sem interceptar requisições com `page.route`. O ensaio de HUD mede os textos e placas dos jogos revisados em três tamanhos de tela, com cobertura separada dos resultados e reinícios.

`tests/e2e_rotated_gameplay.py` abre quatro jogos reais pelo portal em um celular de 390×844, aceita o diálogo para girar a área e envia gestos de navegador. Confere deslocamento do canhão, encaixe de peça, movimento no futebol e subida/descida sustentada da raquete. A imagem, o estado do jogo e as amostras por quadro ficam no relatório; o ensaio usa o SDK do Telegram em modo visitante, sem substituir API ou mecânica.

`tests/e2e_live_ranking.py` faz a integração adicional do portal com a API e o SQLite reais da instância isolada `tests/load_app.py`: identidade sintética assinada, intervalo de atividade real, resultado nativo, confirmação de nova rodada, nova partida distinta e pontos persistidos visíveis na classificação. Apenas o SDK do Telegram é substituído; as rotas da API não são interceptadas. Usar porta e banco exclusivos, nunca a instância pública.

`tests/e2e_native_ranking.py` verifica a continuidade da classificação nos replays próprios de Sudoku e Pênaltis. O primeiro prepara uma grade quase resolvida e usa a última tecla real; o segundo abre o ramo nativo de vitória já verificado na campanha. Cada replay precisa criar outra partida por HTTP, sem substituir respostas da API.

O GitHub Actions executa a suíte completa, as jornadas do portal nos três navegadores e a inicialização da imagem Docker em pushes para `main`, branches `codex/**` e pull requests. As dependências de teste estão fixadas nas versões utilizadas. A matriz completa dos jogos e a carga isolada têm seus comandos próprios acima; não são substituídas pela verificação do portal no CI.

## Capacidade e tempo de abertura

`scripts/load_test_k6.js` usa identidades sintéticas assinadas, sessões e partidas reais da API, banco isolado e perfis dos arquivos realmente carregados pelos jogos. `tests/load_app.py` recusa o token de produção e exige `BALTIGO_LOAD_TEST=1`. Os geradores aceitam apenas endereços locais. Não executar carga contra usuários ou dados públicos.

O perfil de qualificação tem 1.200 usuários, rampa de 60 segundos, no mínimo 180 segundos reais com todas as partidas ativas, atividade a cada dez segundos, ranking a cada 30 segundos e finalização distribuída em 30 segundos. A execução de qualificação usa `HOLD=210`, incluindo margem de início; a janela real precisa ser conferida pelos timestamps do banco. Todos devem começar e terminar sem erros, com pontos persistidos. As metas são p95 abaixo de 500 ms e p99 abaixo de 1.500 ms para atividade e ranking; p95 abaixo de 2.500 ms para abertura HTTP com cache inicialmente vazio. Manter as metas e guardar também os resultados reprovados.

Registrar versão do código, hardware, limites de CPU/memória, Python, SQLite e gerador junto com o resultado. Esse perfil verifica HTTP, autenticação e persistência; não simula 1.200 renderizadores gráficos, aparelhos físicos, tráfego público da internet ou polling do Telegram. O tempo de abertura registrado no navegador inclui inicialização gráfica; o tempo HTTP da carga mede outra parte do fluxo.

## Telegram e operação

O bot apresenta um banner de abertura e fotos dos próprios jogos em português, com emojis escolhidos para os textos e todos os botões. `/home` apresenta o fliperama e seus atalhos. `/games` mostra o catálogo com seis jogos por página, filtros por categoria e busca inline. `/jogar` sugere uma partida com foto, objetivo e abertura direta; `/jogar tetris` encontra o jogo pelo nome ou identificador. O botão para trocar a sugestão escolhe outro jogo quando há alternativas. Os menus se atualizam na própria mensagem pelos botões de navegação.

`/start` abre as boas-vindas; `/start game_<slug>` continua abrindo o jogo específico compartilhado. A pesquisa inline mostra capas, categoria, objetivo e botão de abertura, com busca sem distinção de acentos e paginação de todo o catálogo. As fotos e miniaturas JPEG estão em `web/telegram/`; `scripts/build_telegram_media.py` reproduz os arquivos a partir das capas locais e da composição original do banner. `manifest.json` registra dimensões, tamanhos e hashes.

Em qualquer conversa, digite `@BaltigoGamesBot` e o nome do jogo para escolher uma foto. O botão **Abrir catálogo de jogos**, acima dos resultados, abre o Mini App diretamente no modo inline, inclusive em grupos. Nesse modo o Telegram não fornece identidade autenticada: é possível jogar como visitante, mas as partidas não entram na classificação autenticada. O botão Compartilhar do portal usa a escolha de conversa do Telegram quando disponível; navegadores comuns mantêm compartilhamento nativo ou cópia do link.

Para que o botão da própria foto abra diretamente o jogo, o proprietário deve configurar o **Main Mini App** no BotFather apontando para `APP_URL`. O bot consulta `getMe.has_main_web_app` ao iniciar. Enquanto a opção estiver desativada, o botão informa **Abrir jogo no bot** e usa `/start game_<slug>`; na conversa privada, **Jogar agora** abre o jogo escolhido. Reinicie somente o serviço do bot após alterar a configuração no BotFather. Para um Mini App nomeado já configurado, `TELEGRAM_MINI_APP_SHORT_NAME` pode informar seu identificador real; não definir um nome inventado.

Botões `web_app` de mensagens são exclusivos da conversa privada com o bot. Mensagens em grupos e fotos inline usam links de Mini App ou a alternativa privada acima. Isso não exige tornar o bot administrador ou desativar a privacidade do grupo, e não oferece partidas multiplayer. A suíte do bot valida os conteúdos e destinos sem enviar mensagens reais; `tests/e2e_inline_launch.py` simula os recursos do cliente Telegram nos três navegadores e testa o portal real. A entrega de fotos e a abertura dentro do aplicativo Telegram precisam também de conferência no dispositivo.

O bot registra comandos, descrição e botão de menu em português. `/health` falha se o bot configurado não estiver em execução. Inline Mode e Main Mini App são opções da conta no BotFather e não podem ser habilitadas pelo token.

Na inicialização, o bot lê o perfil, as descrições, os comandos e o menu antes de atualizar somente os campos diferentes. Se o Telegram limitar essa configuração opcional com `RetryAfter`, o lote é adiado e as partidas e o polling continuam disponíveis. A próxima inicialização ou uma reconciliação explícita após o intervalo informado tenta apenas as diferenças restantes; não há repetição em laço durante a limitação. Falhas de autenticação, inicialização e polling continuam sendo propagadas.

O atendimento permite até 64 atualizações simultâneas, mantendo a ordem de cada conversa. O limite inclui solicitações que aguardam a mesma conversa; não é um agendador com distribuição justa sob inundação. As fotos são enviadas dos arquivos locais e, após a confirmação, reutilizam o `file_id` do Telegram em memória. O cache é limitado e recomeça a cada inicialização. Se o arquivo local estiver ausente, a URL pública continua sendo a alternativa. Menus com a mesma foto confirmada atualizam somente a legenda e os botões, sem baixar ou reenviar a imagem. A confirmação é por mensagem: snapshots antigos de callbacks não servem como prova da foto atual. Uma rejeição definitiva de identificador inválido permite uma recuperação; timeouts, erros de rede e limites não causam reenvios incertos. O log registra operação, transporte e duração sem texto, argumentos, identificadores de conversas ou credenciais.

Falhas temporárias de rede nas consultas ou atualizações opcionais de perfil também interrompem somente esse lote, com registro da operação e classe do erro, sem repetição. Uma atualização cuja resposta expirou é reconciliada pela leitura na próxima inicialização. Rejeições de configuração (`BadRequest`), erros de autenticação e permissões continuam sendo propagados; a tolerância não se aplica à inicialização, autenticação, polling ou execução do bot.

Consulte `deploy/README.md` para publicação, persistência e recuperação. Não colocar o token no repositório, nas capturas ou nos logs.

## Licenças e referências

A licença MIT da fonte está em `LICENSE`; licenças das bibliotecas e fontes estão em `web/vendor/LICENSES.json`, `web/fonts/` e `licenses/`. As capas são capturas da versão MIT dos jogos; os SVGs de fundo e da interface são originais.

Referências de navegação e apresentação: [Poki Brasil](https://poki.com/br), [CrazyGames Brasil](https://www.crazygames.com/br/), [PICO-8](https://www.lexaloffle.com/pico-8.php) e [Playdate](https://play.date/). A integração segue a documentação de [Telegram Mini Apps](https://core.telegram.org/bots/webapps).
