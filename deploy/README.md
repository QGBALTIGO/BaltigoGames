# Operação VPS Baltigo Games

URL pública: https://games.187-77-255-164.sslip.io/ — bot: https://t.me/BaltigoGamesBot.

O serviço `baltigogames.service` usa o usuário `baltigogames`, um processo na porta local 8056 e o ambiente Python exclusivo `/opt/baltigogames/venv`. O link `/opt/baltigogames/current` aponta para uma versão em `releases/`. O arquivo privado `/opt/baltigogames/.env` pertence a root, permissão 600.

O mirror de jogos fixado está em `/opt/baltigogames/upstream/c97ef8b`, com manifesto de SHA-256. O ranking fica em `/var/lib/baltigogames/leaderboard.sqlite`, diretório privado criado pelo `StateDirectory` do serviço. **Preservar esse banco em toda atualização.** Favoritos e histórico continuam no armazenamento do dispositivo.

Configuração de produção adicional:

```env
UPSTREAM_LOCAL_DIR=/opt/baltigogames/upstream/c97ef8b
DATABASE_PATH=/var/lib/baltigogames/leaderboard.sqlite
```

O bot e o site compartilham um processo; não aumentar `--workers`. Dois processos com o mesmo token causam conflito no Telegram. `/health` retorna 503 se o catálogo estiver vazio ou o bot configurado parar. O processo aborta se não conseguir iniciar o bot. A unidade permite 2.048 conexões concorrentes, keep-alive de dois segundos e 8.192 descritores, mantendo um único worker, CPU máxima de um núcleo e memória de 768 MiB.

O Nginx usa `/etc/nginx/sites-available/baltigogames`. O cache público está em `/var/cache/baltigogames-v2`, até 512 MiB, reservado a `/play/` e `/play-v2/`. O cache v2 substitui o anterior para impedir reaproveitamento de documentos antigos em inglês. O player usa `/play-v2/` para que o cache HTTP dos dispositivos também carregue a versão nova, incluindo scripts e configurações relativos. APIs autenticadas e o banco não entram no cache. O certificado Let's Encrypt tem renovação automática; manter acessível `/.well-known/acme-challenge/` no HTTP.

## Atualização e recuperação

1. Confirmar versão, PID, diretório de trabalho, serviço e resposta pública. Guardar a lista dos serviços vizinhos ativos.
2. Fazer backup privado da configuração, unidade e versão ativa. Se o banco existir, usar `sqlite3.Connection.backup()` com o destino dentro de `backups/`, com permissão 600; copiar somente `.sqlite` enquanto há WAL não é backup consistente.
3. Criar uma nova pasta em `releases/`, sem sobrescrever a versão ativa. Manter diretórios de código legíveis pelo usuário do serviço, incluindo os diretórios pais. Os segredos e backups permanecem privados.
4. Instalar dependências no ambiente exclusivo e verificar a versão, o manifesto do mirror, as 142 capas, as fontes, os SVGs e os arquivos vendor.
5. Instalar a unidade, criar o cache como `www-data` e testar a configuração Nginx. Atualizar `current`, reiniciar **somente** `baltigogames.service`; recarregar Nginx se sua configuração mudou.
6. Conferir saúde, catálogo, configuração gratuita, ranking vazio/real, scripts traduzidos, bot/menu e partidas pela URL pública. Confirmar que os serviços vizinhos continuam ativos.

Para recuperar a versão anterior, restaurar o link e, se necessário, a unidade/configuração Nginx previamente guardadas; reiniciar somente Baltigo Games. Preservar o banco atual. Restaurar um backup do banco somente se houver necessidade comprovada, após guardar também o estado atual. Não apagar versões ou backups durante a publicação.

O token não deve aparecer no repositório, nos comandos de diagnóstico ou nos logs. Nunca publicar `.env`, banco ou backups no diretório estático. Diagnósticos do Telegram devem resumir apenas estado e rótulos públicos.

## Verificação antes de publicar

Com o mirror pronto, iniciar um servidor isolado **sem o token de produção**:

```sh
python scripts/validate_catalog.py
pytest -q
python tests/e2e_portal.py
python scripts/audit_games.py --base http://127.0.0.1:8190 --profiles preferred,desktop --covers --workers 2 --output artifacts/qualification-preferred
python scripts/audit_round_transitions.py --base http://127.0.0.1:8190 --phaser-only --workers 2 --out artifacts/terminal-rounds
python tests/e2e_native_rounds.py
python tests/e2e_native_football_hex.py --base http://127.0.0.1:8190
python tests/e2e_authored_campaigns.py --base http://127.0.0.1:8190
python tests/e2e_authored_remaining_campaigns.py --base http://127.0.0.1:8190
python tests/touch_control_audit.py
```

Os navegadores Playwright devem estar instalados. `TEST_BASE_URL` seleciona o endereço dos testes do portal. Manter dados sintéticos apenas em bancos de teste isolados; não semear o ranking público com usuários falsos.

A suíte do portal usa Chromium, Firefox e WebKit, incluindo celular, paisagem e desktop. Simula as APIs do cliente Telegram e a assinatura nos casos de integração isolados. O auditor de jogos retém relatório e captura de cada partida, envia comandos e detecta erros, assets ausentes, controles invisíveis e menus presos. Não equivale a concluir todas as fases nem a homologação em um aparelho físico com Telegram aberto.

`probe_games.py` é apenas verificação HTTP das entradas HTML. Não usar esse resultado como evidência de jogabilidade. A entrada `e2e_gameplay.py` agora executa o auditor completo, não apenas carregamento de exemplos.

## Qualificação de capacidade

Usar uma instância isolada sem `BOT_TOKEN`, com banco, cache e portas exclusivos. `tests/load_app.py` exige `BALTIGO_LOAD_TEST=1` e recusa credenciais do bot. O gerador `scripts/load_test_k6.js` aceita somente loopback e usa 1.200 identidades sintéticas distintas, compartilhando um IP para representar redes de operadora. Não usar a base pública nem o ranking real para carga.

Fixar e registrar a versão e o SHA-256 do k6. Gerar os perfis com `scripts/create_load_manifest.py`: documentos, scripts, fontes e imagens vêm das requisições dos próprios jogos. O cenário completo tem rampa de 60 segundos, permanência de 180 segundos e finalização em 30 segundos. Verificar 1.200 inícios e finais, zero falhas HTTP/aplicativas, integridade SQLite, pontos persistidos e pico real de partidas simultâneas.

As metas de atividade e ranking são p95 < 500 ms e p99 < 1.500 ms. Abertura HTTP com cache vazio deve ter p95 < 2.500 ms. Manter as metas mesmo que um ensaio seja reprovado; guardar relatório, hashes e limites de recursos de cada tentativa. A carga HTTP não verifica renderização gráfica em 1.200 celulares nem latência da internet pública.

Observar continuamente a saúde do serviço real durante o ensaio isolado. Interromper apenas candidato e gerador se houver impacto sustentado. Registrar hardware, versões, CPU/memória, unidades e ausência do token de produção. Antes de ativar uma versão, repetir a carga com os arquivos exatos da versão candidata aprovada.

O Nginx precisa de capacidade de conexões e descritores compatível com o cenário: conferir `worker_connections` de pelo menos 4.096 e `worker_rlimit_nofile` de pelo menos 8.192. Fazer backup do arquivo global, preservar as demais diretivas e sites, executar `nginx -t` e aplicar por recarga graciosa. Recuperar também esse arquivo no rollback quando tiver sido alterado.

## Versões e próxima etapa

A versão atual mantém todos os jogos gratuitos e vidas ilimitadas no portal. Versus, vidas, loja e pagamentos aparecem como planejados; `/api/config` declara essas funções desativadas. Não há cobrança, saldo financeiro ou limitação artificial ativa.

A classificação é por participação com limites no servidor. Pontuação enviada pelo navegador não é prova de desempenho antitrapaça; não usar esse ranking para prêmios financeiros sem validação autoritativa adicional.

Os jogos mantêm suas licenças originais. Correções de código ficam em `app/source_repairs.py`, traduções/adaptação em `app/game_runtime.py` e `web/game-runtime.js`, configurações corrigidas em `data/config-overrides.json`. O mirror original permanece intacto. Os fundos provisórios quadriculados são substituídos apenas nos caminhos explicitamente listados em `data/asset-replacements.json`.
