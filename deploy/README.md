# VPS Baltigo Games

- URL: https://games.187-77-255-164.sslip.io
- Bot: https://t.me/BaltigoGamesBot
- Instalação: `/opt/baltigogames`
- Processo: `baltigogames.service`, usuário `baltigogames`, porta local `8056`.
- Configuração privada: `/opt/baltigogames/.env`, dono root, permissão `600`.
- Versões: `/opt/baltigogames/releases/`, com link `current` para a versão ativa.
- Python: ambiente exclusivo em `/opt/baltigogames/venv`.
- Nginx: `/etc/nginx/sites-available/baltigogames`.
- Cache público de jogos: `/var/cache/baltigogames`, limitado a 512 MiB.

O bot e o webapp compartilham um único processo. Não aumentar `--workers`:
duas instâncias usando long polling causam conflito no Telegram.
O serviço inicia automaticamente no boot e reinicia quando o processo falha.
`/health` retorna `503` se o catálogo estiver vazio ou o bot configurado parar.
Falha na inicialização do bot encerra a inicialização do serviço.

O certificado Let's Encrypt tem renovação automática. A rota HTTP
`/.well-known/acme-challenge/` deve continuar acessível para renovação.
O token não deve ser colocado em repositórios, comandos de diagnóstico ou logs.

## Atualização e recuperação

1. Criar uma nova pasta em `releases/`, sem sobrescrever a versão ativa.
2. Instalar as dependências no ambiente exclusivo e executar os testes abaixo.
3. Guardar cópia da configuração Nginx e do serviço antes de alterá-los.
4. Atualizar o link `current`, verificar `nginx -t` e reiniciar somente
   `baltigogames.service`. Recarregar Nginx somente se sua configuração mudou.
5. Conferir `/health`, `/api/catalog`, bot, menu e jogos pela URL pública.

Para recuperar uma versão anterior, apontar `current` para a pasta anterior e
reiniciar somente o serviço Baltigo Games. Não apagar versões e backups durante
a publicação. Favoritos e histórico ficam no armazenamento local do dispositivo,
separados pelo identificador Telegram; não existe banco de usuários no servidor.

## Bateria de testes

```sh
python scripts/validate_catalog.py
pytest -q
python tests/e2e_smoke.py
python tests/e2e_matrix.py
python tests/e2e_gameplay.py
python scripts/probe_games.py
```

Os testes de navegador exigem Playwright e seus navegadores instalados. Use
`TEST_BASE_URL` para testar a URL pública; o padrão é `http://127.0.0.1:8186`.
Os hooks do cliente Telegram são simulados nos testes de interface. Isso não
equivale a homologação em um celular físico com Telegram aberto.

`probe_games.py` verifica as 142 entradas HTML, não todas as jogadas de todos os
jogos. `e2e_gameplay.py` carrega jogos representativos das dez categorias e
verifica erros JavaScript e falhas de assets.

## Compatibilidade com a fonte dos jogos

O upstream contém configurações com preloads de arquivos ausentes.
`data/config-overrides.json` mantém cópias corrigidas de 40 configurações,
removendo 134 referências inexistentes e preservando os demais parâmetros.
O campo `source_tree` identifica a árvore usada na revisão. Para atualizar essa
evidência, executar `scripts/repair_upstream_configs.py`, revisar as diferenças
e repetir a bateria de testes. O proxy também usa a cópia de Outfit do Snake
quando outro jogo aponta para uma cópia inexistente dessa fonte.

Os arquivos dos jogos continuam vindo de `sausi-7/games`; o cache Nginx reduz
requisições repetidas. Uma indisponibilidade prolongada da fonte pode afetar
arquivos ainda não armazenados em cache.

O bot já suporta modo inline. Sem Main Mini App cadastrada no BotFather, os
links de compartilhamento usam `/start game_<slug>`, que oferece o botão do jogo.
Depois de configurar a Main Mini App, o bot passa a usar links `?startapp=<slug>`
no próximo início. A abertura pelo menu e pelos comandos funciona em ambos os
casos.
