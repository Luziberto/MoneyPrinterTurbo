# Pipeline — Curiosidades do Japão (v2)

Camada editorial que decide **o que gerar**. O MoneyPrinterTurbo continua sendo apenas a fábrica de render (API HTTP).

## Pré-requisitos

1. API do MoneyPrinterTurbo rodando (`python main.py` ou container `api`)
2. [`config.toml`](../config.toml) configurado (OpenAI, Pexels, voz, etc.) — **somente ambiente/infra**
3. **Nenhuma API key neste pipeline** — as chaves ficam no MoneyPrinterTurbo

## Canal vs Env

| Camada | Onde | Conteúdo | Versionado |
|---|---|---|---|
| **Canal** | `pipeline/channels/{slug}/` | Identidade, formato de produção, prompt editorial | Sim (Git) |
| **Fila** | `pipeline/data/pipeline.db` | Temas, status, task_id, video_path | Não (gitignore) |
| **Env** | `config.toml` | API keys, Collector URL, Redis, codec | Não (local) |
| **WebUI** | `config.ui` | Sandbox para testes ad-hoc | Opcional/local |

**Regra:** o orchestrator **nunca** lê prompt, voz ou `video_source` do `config.toml`. Tudo editorial vem do canal; a API recebe o payload HTTP montado pelo pipeline.

### Stock Video Collector (opcional)

Para usar clipes locais em cache:

1. Suba o serviço **Stock Video Collector** e monte o volume compartilhado no container `api` (ver [`docker-compose.yml`](../docker-compose.yml)).
2. Em [`config.toml`](../config.toml) (bloco `[app]`): `collector_base_url`, `collector_remote_dir`, `collector_local_dir`, `collector_fallback_source`.
3. No canal (`channel.json`): `video_source = "collector"` quando o Collector estiver no ar.

O MPT busca por keyword via `GET /clips/search`, copia clipes para o cache da task e complementa com `stock` se a duração local for insuficiente.

## Estrutura

```
pipeline/
├── settings.toml              # API URL, polling
├── data/
│   └── pipeline.db            # fila de temas (gitignored)
├── orchestrator.py
├── lib/
│   ├── channel.py             # load_channel() — channel.json + script_prompt.md
│   ├── topic_store.py         # SQLite topic queue
│   ├── schema.sql
│   ├── categories.py
│   ├── topics.py              # prepare_topic(), status transitions
│   └── music.py
├── scripts/
│   ├── migrate_to_channel_v2.py  # one-shot: profile+preset → canal, topics.json → SQLite
│   ├── migrate_categories.py
│   ├── assign_music_profiles.py
│   └── generate_topics.py
├── assets/music/              # BGM por perfil
└── channels/japao/
    ├── channel.json           # identidade + produção
    └── script_prompt.md       # prompt editorial longo
```

## Responsabilidades editoriais

**Categoria não é runtime. Categoria é editorial.**

```
Tema → Categoria → Música     (SQLite + orchestrator)
Tema → GPT → Roteiro          (API MoneyPrinterTurbo — sem category)
```

| Quem | O que faz |
|---|---|
| **Gerador de temas** | Insere `category` + `topic` no SQLite |
| **Orchestrator** | Valida e consome — **nunca classifica** categoria |
| **GPT de roteiro** | Recebe só `video_subject` — **não conhece** `category` |

Categorias permitidas (inglês): `culture`, `society`, `transport`, `education`, `work`, `food`, `tourism`, `technology`, `history`, `weird_facts`. Ver [`lib/categories.py`](lib/categories.py).

## Convenção de idioma

| Elemento | Idioma |
|---|---|
| Código, chaves JSON, `category` | Inglês |
| `topic`, `script_prompt.md`, roteiro | Idioma do canal (pt-BR no `japao`) |
| Prompt de `generate_topics.py` | Inglês (instruções + JSON) |

## Comandos

```bash
# Próximo tema pendente
python pipeline/orchestrator.py --channel japao --dry-run

# Gerar vídeo
python pipeline/orchestrator.py --channel japao

# Estatísticas
python pipeline/orchestrator.py --channel japao --stats

# Aprovar após revisar o vídeo
python pipeline/orchestrator.py --channel japao --approve 1

# Retentar tema que falhou
python pipeline/orchestrator.py --channel japao --retry 1

# Preparação (não runtime)
python pipeline/scripts/generate_topics.py --channel japao --dry-run
python pipeline/scripts/assign_music_profiles.py --channel japao
```

### Migração legada (profile.toml + preset + topics.json)

Se ainda tiver arquivos antigos:

```bash
python pipeline/scripts/migrate_to_channel_v2.py --channel japao --remove-legacy
```

## Rodar dentro do Docker

```bash
docker exec -it moneyprinterturbo-api python3 pipeline/orchestrator.py --channel japao --dry-run
docker exec -it moneyprinterturbo-api python3 pipeline/orchestrator.py --channel japao
```

## Cron (3 vídeos/dia)

```cron
0 8,14,20 * * * docker exec moneyprinterturbo-api python3 /MoneyPrinterTurbo/pipeline/orchestrator.py --channel japao >> /var/log/mpt-pipeline.log 2>&1
```

## Ciclo de vida do tema

| Status | Significado |
|---|---|
| `pending` | pronto para gerar |
| `processing` | geração em andamento |
| `generated` | vídeo pronto, aguarda revisão |
| `failed` | falhou — use `--retry` |
| `approved` | revisado, ok para publicar |
| `published` | reservado para v2 |

## Onde ficam os vídeos

- Render: `storage/tasks/{task_id}/final-1.mp4`
- Meta: `pipeline/runs/{timestamp}_japao/meta.json`

## Prompt da IA

O orchestrator envia `video_script_prompt` de `script_prompt.md` (com `{niche}` substituído). **Não** envia `custom_system_prompt`.

| Campo | Origem |
|---|---|
| `niche`, `voice_name`, `font_name`, `video_source` | `channel.json` |
| `video_script_prompt` | `script_prompt.md` |
| `paragraph_number`, legendas, `video_aspect` | `channel.json` |

### Vídeo de stock

`video_source` no `channel.json` (ex.: `"pexels"`). API keys em `config.toml`.

| Valor | Comportamento |
|---|---|
| `pexels` / `pixabay` / `coverr` | Um provider de stock por geração |
| `collector` | Cache local via Stock Video Collector |
| `local` | Arquivos locais |

### TTS / voz

Configure `voice_name` em `channel.json`. ElevenLabs: `elevenlabs:voice_id:name` + `elevenlabs_api_key` em `config.toml`.

## Música de fundo

Cada tema no SQLite tem `music_profiles` — pool editorial por vídeo. O orchestrator escolhe um perfil e um arquivo aleatório na biblioteca local de música por perfil.

A localização padrão pode ser `pipeline/assets/music/`, mas os arquivos de áudio são tratados como biblioteca local de ambiente e não devem ser versionados. No app principal, o diretório pode ser configurado por `bgm_profile_music_dir` em `config.toml` ou pela variável de ambiente `BGM_PROFILE_MUSIC_DIR`.

```bash
python pipeline/scripts/assign_music_profiles.py --channel japao
python pipeline/scripts/generate_topics.py --channel japao --overwrite
```

## Regra editorial

**1 curiosidade = 1 vídeo.** Cada tema é uma pergunta única na fila SQLite.

## Novo canal

1. Criar `pipeline/channels/{slug}/channel.json` + `script_prompt.md`
2. Gerar temas: `python pipeline/scripts/generate_topics.py --channel {slug}`
3. Rodar: `python pipeline/orchestrator.py --channel {slug}`
