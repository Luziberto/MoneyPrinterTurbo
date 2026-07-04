# Plano: Cockpit Multi-Canal + Melhorias Editoriais

**Data:** 2026-07-04  
**Base:** `main` atualizado (+38 commits upstream) + trabalho local (pipeline, collector, BGM)  
**Objetivo:** Evoluir a WebUI para cockpit de operador e reforçar qualidade editorial sem reescrever em Vue.

---

## Estado após merge

| Área | Status |
|------|--------|
| Upstream | TwelveLabs, `match_materials_to_script`, Chatterbox TTS, CLI expandido, CI |
| Local preservado | `pipeline/`, `collector_client`, `bgm.py`, prompts BR, `channel.json` |
| Merge resolvido | `task.py`, `material.py`, `llm.py`, `voice.py`, `webui/Main.py`, `config.example.toml` |

**Próximo passo imediato:** validar com `uv run pytest test/` antes de implementar fases abaixo.

---

## Arquitetura alvo

```
┌─────────────────────────────────────────────────────────────┐
│  WebUI Streamlit (cockpit)                                  │
│  Criar │ Canais │ Tarefas │ Config                          │
└───────────────┬─────────────────────────────────────────────┘
                │ preview / smoke test
                ▼
┌─────────────────────────────────────────────────────────────┐
│  pipeline/orchestrator + channel.json + topic_store         │
└───────────────┬─────────────────────────────────────────────┘
                │ jobs
                ▼
┌─────────────────────────────────────────────────────────────┐
│  Stock Video Collector → clips ordenados                      │
└───────────────┬─────────────────────────────────────────────┘
                │ render
                ▼
┌─────────────────────────────────────────────────────────────┐
│  MPT app/services (task, video, voice, bgm)                 │
└─────────────────────────────────────────────────────────────┘
```

A WebUI **não substitui** o pipeline batch — serve para testar canal, ver saúde e debugar jobs.

---

## Fase 1 — Cockpit UI (1–2 semanas)

### 1.1 Reorganizar `webui/Main.py` em abas

| Aba | Conteúdo |
|-----|----------|
| **Criar vídeo** | Fluxo atual (roteiro → mídia → voz → legendas → gerar) |
| **Canais** | Lista `pipeline/channels/*/channel.json`, tópicos SQLite, carregar no form |
| **Tarefas** | Lista de tasks com status, pasta, download MP4 |
| **Configuração** | LLM, voz, API keys (sub-abas ou expanders) |

**Arquivos:** `webui/Main.py`, `webui/i18n/pt.json`, `webui/i18n/en.json`

### 1.2 Seletor de canal no topo

- Ler canais via `pipeline/lib/channel.py` → `list_channels()` (criar helper se não existir)
- Ao selecionar canal, pré-preencher:
  - `video_source` (default: `collector`)
  - `bgm_profile`
  - `voice_name`, `video_aspect`, `paragraph_number`
  - `match_materials_to_script`
  - prompt editorial (`custom_system_prompt` do canal)
- Persistir em `st.session_state["active_channel"]`

**Arquivos:** `webui/Main.py`, `pipeline/lib/channel.py`

### 1.3 Central de provedores (padrão Cenara)

Grid `st.metric()` com readiness:

| Provedor | Checagem |
|----------|----------|
| LLM | provider + api key configurados |
| Collector | `collector_client.check_collector_health()` |
| TTS | voz selecionada + credenciais do servidor ativo |
| FFmpeg | `shutil.which("ffmpeg")` ou `IMAGEIO_FFMPEG_EXE` |
| BGM | perfis em `bgm_service.list_profiles()` |

**Referência:** `clones/gxeon-avatar-video-forge/webui/Main.py` → `cenara_render_provider_center`

### 1.4 Progresso de geração com `st.status()`

Etapas visíveis:

1. Validar provedores  
2. Gerar roteiro / termos  
3. TTS  
4. Collector / download  
5. Montagem  
6. Finalizar  

Opcional v1: tail do log em `storage/tasks/<task_id>/` com refresh a cada 2s.

**Referência:** Coiner `LogViewer.vue` (conceito; implementação Streamlit simples)

### 1.5 Preview gate (antes do render caro)

Botão **“Gerar preview”** que só executa:

- `llm.generate_script` + `llm.generate_terms`
- `voice.tts` (opcional checkbox “incluir áudio”)

Botão **“Renderizar vídeo completo”** dispara `tm.start()` só após preview OK.

---

## Fase 2 — Editorial (2–3 semanas)

### 2.1 `match_materials_to_script` por canal

**Já mergeado no motor.** Falta:

- Campo `match_materials_to_script: bool` em `channel.json`
- `pipeline/orchestrator.py` → passar flag no `VideoParams`
- Checkbox na WebUI (aba Criar) com tooltip
- Teste: `test/pipeline/test_channel_runtime.py` valida default por canal

**Referência:** `clones/madrasmillennial/app/services/material.py`

### 2.2 Cards de opção (VisualAI spec 001)

Substituir selectboxes por cards clicáveis (CSS inline) para:

- Fonte de vídeo (Collector / Pexels / Local)
- Aspecto (9:16 / 16:9)
- Perfil BGM

**Referência:** `clones/visualai-rendering-engine/specs/001-nexcognit-ui-style/spec.md`

### 2.3 Diagnóstico pós-render de clipes

Após `tm.start()`, exibir card:

- Fontes únicas usadas vs total de segmentos
- Clipes repetidos (mesmo `source_file_path`)
- Avisos do collector (jobs parciais, fallback)

**Referência:** `clones/visualai-rendering-engine/docs/POSTMORTEM_2026-05-26_clip_repetition.md`

### 2.4 Aba Canais — integração topic_store

- Listar tópicos: `pending` / `used` por canal
- Botão “Carregar tópico #N” → preenche subject + script no form
- Mostrar `uid`, `topic_id`, `music_profile`, `category`

**Arquivos:** `webui/Main.py`, `pipeline/lib/topic_store.py`

---

## Fase 3 — Robustez e escala (quando batch crescer)

### 3.1 `runtime_limits` (Cenara)

- `app/services/runtime_limits.py` — caps por env (`MAX_THREADS`, `MAX_REMOTE_MB`, etc.)
- Lock de geração + botão “Limpar geração travada” na WebUI

**Referência:** `clones/gxeon-avatar-video-forge/app/services/runtime_limits.py`

### 3.2 Painel de tarefas completo

- `st.dataframe` ou cards: `task_id`, estado, %, criado em
- Ações: abrir pasta, baixar MP4, cancelar (se API suportar)
- Estatísticas: total / rodando / falhou / concluído

**Referência:** Coiner `TaskManagement.vue`

### 3.3 Rerank semântico pós-collector (SigLIP)

**Não usar TwelveLabs como default** (custo ~$90/render em long-form).

Ordem de adoção:

1. Collector retorna N candidatos por keyword/segmento  
2. Rerank local SigLIP escolhe o melhor  
3. Render recebe lista ordenada (contrato `pre_signed_clip_urls` / structured clips)

**Referência:** `clones/visualai-rendering-engine/specs/022-siglip-reranker/`

### 3.4 Registry de modos (VisualAI)

- `app/services/modes/` com `faceless`, `long_form` (futuro)
- `channel.json` → `"mode": "faceless"` mapeia defaults editoriais

**Referência:** `clones/visualai-rendering-engine/app/services/modes/`

---

## Fase 4 — Opcional (backlog)

| Item | Fonte | Quando |
|------|-------|--------|
| Multi-cena (`scene_parser`) | Coiner | Canal com intro/corpo/CTA |
| Title overlay | Coiner | Branding por canal |
| Polish mode de roteiro | VisualAI spec 013 | Brief criativo → hook/corpo/CTA |
| BGM audit warning | VisualAI spec 011 | Falha silenciosa de mix |
| Long-form 2–5 min segmentado | VisualAI spec 016 | Canal YouTube landscape |

---

## O que NÃO fazer

- Migrar WebUI para Vue (Coiner) — custo alto, pipeline é headless
- Copiar UI Cenara inteira — inchada e duplica MPT
- TwelveLabs como rerank default — usar SigLIP local
- Survival render como caminho principal — degrada qualidade
- Merge de forks inteiros — cherry-pick por feature

---

## Ordem de PRs sugerida

| PR | Escopo | Risco |
|----|--------|-------|
| PR-1 | Abas + seletor de canal + load defaults | Baixo |
| PR-2 | Central de provedores + `st.status()` | Baixo |
| PR-3 | Preview gate | Médio |
| PR-4 | Aba Canais + topic_store | Médio |
| PR-5 | `match_materials_to_script` no orchestrator + channel.json | Baixo |
| PR-6 | Diagnóstico pós-render de clipes | Baixo |
| PR-7 | Cards de opção (CSS) | Baixo |
| PR-8 | Painel de tarefas | Médio |
| PR-9 | `runtime_limits` | Médio |
| PR-10 | SigLIP reranker | Alto |

---

## Critérios de aceite por fase

### Fase 1
- [ ] Operador seleciona canal `japao` e form pré-preenche collector + BGM profile
- [ ] Readiness mostra Collector offline antes de gerar
- [ ] Preview gera roteiro sem disparar collector
- [ ] Abas não quebram fluxo manual existente

### Fase 2
- [ ] Canal com `match_materials_to_script: true` gera B-roll na ordem do roteiro
- [ ] Aba Canais lista tópicos e carrega um no form
- [ ] Pós-render mostra contagem de fontes únicas

### Fase 3
- [ ] Batch de 10 vídeos não trava WebUI (lock + limites)
- [ ] Lista de tarefas mostra status sem abrir pasta manualmente

---

## Comandos úteis

```bash
# Validar após cada PR
uv run pytest test/services/ test/pipeline/ -q

# Smoke WebUI
./webui.sh

# Smoke pipeline
uv run python pipeline/orchestrator.py --channel japao --dry-run

# Collector health
uv run python -c "from app.services import collector_client; print(collector_client.check_collector_health())"
```

---

## Referências rápidas nos clones

| Ideia | Clone | Arquivo |
|-------|-------|---------|
| Provider center + stepper | Cenara | `clones/gxeon-avatar-video-forge/webui/Main.py` |
| Task list + logs | Coiner | `clones/Coiner/vue-frontend/src/views/TaskManagement.vue` |
| match script order | madrasmillennial | `app/services/material.py` |
| SigLIP rerank | visualai | `specs/022-siglip-reranker/` |
| Modos registry | visualai | `app/services/modes/` |
| Postmortem clipes | visualai | `docs/POSTMORTEM_2026-05-26_clip_repetition.md` |
