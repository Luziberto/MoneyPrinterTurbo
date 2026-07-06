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

### Stock Video Collector

Fluxo oficial para clipes em cache:

```
MoneyPrinterTurbo → POST /stock/jobs → Collector → status: ready → render → MP4
```

**Milestone de validação:** 1 vídeo real do canal com `video_source = "collector"`, MP4 final com clipes do Collector, sem fallback para Pexels e sem erro de path.

#### Setup recomendado (Collector no host, MPT no Docker)

Magnific ainda exige browser headed no host; até o fluxo rodar com confiança no Docker, use:

```bash
# Terminal 1 — Collector
cd ../Stock-Video-Collector && ./run-host.sh   # :8001

# Terminal 2 — MPT
docker compose up -d --build
```

**`config.toml`** (bloco `[app]`):

```toml
collector_base_url = "http://host.docker.internal:8001"
collector_remote_dir = "/data/downloads"
collector_local_dir = "/data/downloads"
collector_job_timeout_seconds = 600
collector_enable_legacy_fallback = false
```

O `docker-compose.yml` monta `../Stock-Video-Collector/data/downloads` em `/data/downloads:ro` no container `api` e define `extra_hosts` para `host.docker.internal`.

No canal (`channel.json`): `"video_source": "collector"`.

#### Path gate (antes do primeiro vídeo real)

Após um smoke job `ready`, cada clipe deve retornar path canônico:

```bash
curl -s http://localhost:8001/stock/jobs/<job_id> | jq '.clips[].path'
# Esperado: /data/downloads/arquivo.mp4
```

O Collector normaliza paths host-absolutos para `/data/downloads/...` na resposta da API.

#### Smoke test rápido (~15s, sem gastar quota Magnific)

Para validar a integração sem pedir 25 clipes nem roteiro longo, use keywords que já estão no cache e poucos clipes no `channel.json`:

```json
"collector": {
  "target_clips": 3,
  "min_acceptable_clips": 2
}
```

```bash
docker exec moneyprinterturbo-api python3 cli.py \
  --video-subject "Tokyo street smoke test" \
  --video-script "Você já viu as luzes neon de Tokyo à noite? As ruas ficam cheias de gente. É um espetáculo único no mundo." \
  --video-source collector \
  --video-terms "Tokyo street" \
  --paragraph-number 1 \
  --no-match-materials-to-script \
  --video-clip-duration 3 \
  --voice-name "pt-BR-AntonioNeural-Male" \
  --voice-rate 1.15 \
  --bgm-type none \
  --task-id collector-e2e-15s
```

Critério: job `ready` com `local_reused > 0` e `new_downloads = 0`, MP4 em `storage/tasks/<task_id>/final-1.mp4`.

#### Fallback

Com `collector_enable_legacy_fallback = false` (padrão), falha explícita se o Collector estiver indisponível — não cai silenciosamente para Pexels. O waterfall Magnific → Pexels → Pixabay roda **dentro** do Collector, não no MPT.

Chaves de API (Magnific/Pexels/Pixabay) ficam no Collector (`data/config/config.json`), não no MPT.

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
| `published` | publicado via `--publish` |

## Publicação (Upload-Post)

Um canal editorial (`japao`) define **onde** publicar em `publish_profiles` no `channel.json`. Credenciais Upload-Post ficam em `config.toml` (`upload_post_api_key`, `upload_post_username`).

`platform_targets` é legado — o fluxo novo usa `publish_profiles`. Plataformas suportadas hoje: `youtube`, `tiktok`, `instagram`. `facebook` e `kwai` ficam desabilitados até haver integração.

```bash
# Aprovar vídeo gerado
python pipeline/orchestrator.py --channel japao --approve 42

# Publicar manualmente (usa publish_profiles do canal)
python pipeline/orchestrator.py --channel japao --publish 42
```

Configuração inicial recomendada:

```toml
upload_post_enabled = false
upload_post_platforms = ["youtube"]
upload_post_auto_upload = false
upload_post_youtube_privacy_status = "unlisted"
```

Com `upload_post_auto_upload = true`, o render também publica ao finalizar (via `app/services/publish.py`).

## Onde ficam os vídeos

- Render: `storage/tasks/{task_id}/final-1.mp4`
- Meta: `pipeline/runs/{timestamp}_japao/meta.json`

## Prompt da IA

O orchestrator envia `video_script_prompt` de `script_prompt.md` (com `{niche}` substituído). **Não** envia `custom_system_prompt`.

| Campo | Origem |
|---|---|
| `niche`, `voice_name`, `font_name`, `video_source` | `channel.json` |
| `collector.target_clips`, `collector.min_acceptable_clips` | `channel.json` |
| `video_script_prompt` | `script_prompt.md` |
| `paragraph_number`, legendas, `video_aspect` | `channel.json` |

### Vídeo de stock

`video_source` no `channel.json` (ex.: `"pexels"`). API keys em `config.toml`.

| Valor | Comportamento |
|---|---|
| `pexels` / `pixabay` / `coverr` | Um provider de stock por geração |
| `collector` | Cache local via Stock Video Collector; keywords com `{term, weight}` e limites em `channel.json` → `collector` |
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
