# 🎮 Baltigo Games

Telegram Mini App de jogos web baseada no catálogo open-source **sausi-7/games** (MIT), reconstruída para uma experiência mobile-first dentro do Telegram.

## O que já vem pronto

- **142 jogos** do catálogo Sausi-7, em 10 categorias.
- Busca por nome, categoria, tags e descrição.
- Favoritos e histórico recente separados por usuário Telegram no armazenamento local.
- Player imersivo com Telegram Back Button, fullscreen, haptics e bloqueio de swipe vertical durante a partida.
- Deep link por jogo via `?startapp=<slug>`.
- Compartilhamento pelo modo inline com `switchInlineQuery`.
- Bot com `/start`, `/jogar`, `/games`, botão de menu WebApp e resultados inline.
- Proxy próprio `/play/...` para manter os jogos dentro do domínio do Mini App.
- Docker e Railway prontos, com healthcheck em `/health`.
- Testes automatizados para backend, segurança básica do proxy, hooks do Telegram e integridade do catálogo.

## Configuração de produção

O único **segredo** obrigatório no ambiente é:

```env
BOT_TOKEN=123456:ABC...
```

No Railway, `RAILWAY_PUBLIC_DOMAIN` é detectado automaticamente. `APP_URL` só é necessário se você quiser forçar um domínio diferente.

Variáveis opcionais:

```env
APP_URL=https://games.seudominio.com
UPSTREAM_GAMES_BASE=https://sausi-7.github.io/games
```

## Rodar localmente

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Sem `BOT_TOKEN`, a interface web e as APIs funcionam normalmente e o processo do bot é ignorado.

## Testes

```bash
pip install pytest
python scripts/validate_catalog.py
pytest -q
```

A suíte verifica healthcheck, catálogo, validação contra path traversal no proxy, detecção automática do domínio Railway, ranking da busca inline, presença dos hooks do Telegram e ausência de token hardcoded.

## Telegram

Quando o token é configurado, o bot registra automaticamente:

- comandos `/jogar` e `/games`;
- botão de menu **🎮 Jogos**;
- botão WebApp na conversa privada;
- handler de pesquisa inline;
- resultados inline com botão **▶️ Jogar**;
- deep links como `https://t.me/<bot>?startapp=snake`.

### Configurações únicas no @BotFather

O token é o único segredo que o código precisa, mas duas permissões da plataforma continuam sendo configuradas uma única vez no **@BotFather**:

1. habilitar **Inline Mode** (`/setinline`);
2. cadastrar a **Main Mini App** do bot para que os links `?startapp=...` abram diretamente a Mini App.

Essas opções não são habilitadas pelo token via Bot API.

## Arquitetura dos jogos

O catálogo fica versionado em `data/registry.json`. Por padrão, os assets dos jogos são buscados do upstream Sausi-7 e retransmitidos pelo endpoint `/play/...`. Isso deixa o repositório leve e mantém URLs relativas dos jogos funcionando no mesmo domínio do player.

A fonte pode ser trocada depois por um mirror/CDN próprio alterando `UPSTREAM_GAMES_BASE`, sem mudar a interface ou o bot.

## Fonte e licença

Catálogo/jogos de origem: **sausi-7/games** — MIT.

A licença original é mantida em `LICENSE`. A interface, integração Telegram, backend, proxy, persistência local e experiência mobile foram adaptados para o Baltigo Games.
