# Graph Report - .  (2026-07-09)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2012 nodes · 3586 edges · 142 communities (91 shown, 51 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 235 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ca6b6157`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 134
- Community 141

## God Nodes (most connected - your core abstractions)
1. `tr()` - 65 edges
2. `TestLiteLLMProvider` - 35 edges
3. `TopicStore` - 34 edges
4. `TestVoiceService` - 31 edges
5. `TestVideoService` - 30 edges
6. `ZernioService` - 25 edges
7. `TestCockpitHelpers` - 24 edges
8. `tts()` - 22 edges
9. `TestBedrockProvider` - 20 edges
10. `load_channel()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `TestVideoService` --uses--> `TaskQueueFullError`  [INFERRED]
  test/services/test_video.py → app/controllers/manager/base_manager.py
- `TestVideoService` --uses--> `InMemoryTaskManager`  [INFERRED]
  test/services/test_video.py → app/controllers/manager/memory_manager.py
- `_load_channel_or_404()` --calls--> `load_channel()`  [INFERRED]
  app/controllers/v1/channels.py → pipeline/lib/channel.py
- `_topic_store()` --calls--> `TopicStore`  [INFERRED]
  app/controllers/v1/channels.py → pipeline/lib/topic_store.py
- `TopicStatusUpdate` --uses--> `TopicStore`  [INFERRED]
  app/controllers/v1/channels.py → pipeline/lib/topic_store.py

## Import Cycles
- 1-file cycle: `app/services/modes/__init__.py -> app/services/modes/__init__.py`

## Hyperedges (group relationships)
- **Docker deployment configuration set (base, GPU override, release)** — docker_compose, docker_compose_gpu, docker_compose_release [EXTRACTED 0.85]
- **Multi-language README set (zh/en/ar) documenting the same project** — readme, readme_en, readme_ar [EXTRACTED 0.90]
- **Local setup/run entrypoints referenced across READMEs** — main, cli, webui_sh, webui_bat, webui_main [INFERRED 0.60]

## Communities (142 total, 51 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (62): _anthropic_litellm_model_id(), _bedrock_litellm_kwargs(), _bedrock_litellm_model_id(), _bedrock_mantle_api_base(), _bedrock_mantle_responses(), build_script_prompt(), build_social_metadata_prompt(), _clamp_text() (+54 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (52): apply_title_overlay(), VideoParams, Minimal opening title card for channel branding., _build_structured_subclipped_items(), close_clip(), _coerce_collector_selected_clip(), _collector_min_screen_duration(), combine_videos() (+44 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (26): _bgm_type(), build_video_params(), _hex_color(), _non_negative_float(), _paragraph_count(), parse_args(), _percent_position(), _positive_int() (+18 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (48): get_reranker_kind(), Clip reranking hooks (SigLIP planned; score-based fallback today)., Reorder collector clips for a keyword/segment., rerank_collector_clips(), _aspect_ratio_to_dimensions(), _build_collector_job_request(), _collector_enable_legacy_fallback(), _config_bool() (+40 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (40): build_channel_runtime(), compute_pipeline_step_states(), detect_overrides(), ensure_pipeline_path(), flatten_workspace(), _normalize_runtime_value(), Any, Pure-logic cockpit helpers, ported from webui/cockpit.py's session_state functio (+32 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (29): check_collector_health(), _collector_headers(), _collector_job_timeout(), _collector_poll_interval(), _collector_timeout(), CollectorError, CollectorJobFailedError, CollectorQuotaExceededError (+21 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (18): 验证 LiteLLM provider 的主路径不依赖真实网络和私有 API key。          这里用 fake module 注入 `sys.mod, 某些 OpenAI-compatible 网关在内容过滤或安全拦截时会返回         HTTP 200，但 `choices[0].message` 为, 自定义 OpenAI-compatible base_url 可能包含代理网关的 user:pass。         SDK 抛错时常会把 URL 带回异常信, DashScope chat 模式会把文本放在 `output.choices[0].message.content`。         这里覆盖 issue, 保留旧 DashScope completion 响应结构的兼容路径。, Qwen 空响应应返回可诊断错误，而不是底层 AttributeError。, Qwen chat 响应 choices 为空时应返回明确错误。, AIHubMix 是 OpenAI-compatible 网关。这里用 fake OpenAI client         验证独立 provider 会使用 (+10 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (28): cross_post_video(), Upload-Post API integration for cross-posting videos to TikTok, Instagram and Yo, Check the status of an upload request.          Args:             request_id (st, Read Upload-Post settings from [app], falling back to legacy [ui] keys., _upload_post_setting(), UploadPostService, Read Zernio settings from [app] (no legacy [ui] fallback)., _zernio_setting() (+20 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (35): _atomic_write_lock(), cap_thread_count(), clear_stale_generation_lock(), _env_bool(), _env_int(), generation_lock_path(), generation_lock_status(), GenerationAlreadyRunningError (+27 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (11): ABC, BaseState, MemoryState, Convert values written by this application back to common Python types., Redis-backed task state.      Trust boundary: Redis is expected to be private to, RedisState, _FakeRedis, Redis SCAN 分批返回 key 时，分页切片必须按当前批次起始位置计算。          这个用例复现 PR #890 描述的 18 条任务、page (+3 more)

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (14): cross_post_video(), Zernio API integration for cross-posting videos to TikTok, Instagram and YouTube, Return (platform entries for POST /posts, skipped platform results)., Presign, PUT the file (streamed) and return the public media URL., Map platform -> accountId from GET /accounts (cached per process)., Post-level content doubles as the YouTube description on Zernio.         YouTube, ZernioService, _accounts_response() (+6 more)

### Community 11 - "Community 11"
Cohesion: 0.12
Nodes (21): ping(), Request, new_router(), ConfigPatchRequest, get_config(), put_config(), BaseModel, Request (+13 more)

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (16): local 素材路径来自 API 参数，不能允许任意绝对路径进入 MoviePy。         这里验证非 local_videos 白名单目录内的路径会被, BGM 列表接口现在只暴露文件名；生成视频时应能把文件名安全解析回         resource/songs 白名单目录，保持正常使用路径可用。, 用户在 WebUI 中可能直接填写 ./resource/songs/xxx.mp3。该路径虽然是         项目根目录相对路径，但实际文件仍在 reso, 配置中显式指定 ffmpeg 时，应优先使用该路径。, 用户选择的硬件编码器必须先经过 FFmpeg encoder 列表检测。检测不到         时直接回退 libx264，避免生成任务在写文件阶段才失败。, FFmpeg 声明支持某个硬件编码器，不代表当前显卡或驱动一定可用。         首次实际编码失败后，应立即用 libx264 重试，并在本进程禁用该编码器, 如果 libx264 兜底也失败，失败原因更可能是输出路径、权限、文件占用等         通用问题，不能误判为硬件编码器不可用。, 最终 ffmpeg concat 阶段也要具备同样的回退能力。这里用 mock 模拟         h264_nvenc 编码失败，确认会自动再用 libx2 (+8 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (35): VideoTransitionMode, analyze_clip_materials(), assign_model_fields(), _collector_limits_from_runtime(), detect_overrides(), _format_generated_terms(), _is_terms_error(), _material_source_key() (+27 more)

### Community 14 - "Community 14"
Cohesion: 0.08
Nodes (28): _default_active_step(), ensure_pipeline_path(), _format_script_words_display(), list_available_channels(), load_channel_config(), _parse_target_words_max(), persist_cockpit_textarea(), _pipeline_dot_emoji() (+20 more)

### Community 15 - "Community 15"
Cohesion: 0.08
Nodes (17): analyze_clip(), _client(), _cosine(), embed_text(), _embed_text_cached(), is_enabled(), TwelveLabs (https://twelvelabs.io) integration — optional, opt-in helpers.  This, Reorder `search_terms` so the terms most semantically relevant to     `video_sub (+9 more)

### Community 16 - "Community 16"
Cohesion: 0.10
Nodes (24): get_ffmpeg_binary(), 兼容历史上直接从 video 服务读取 FFmpeg 路径的调用方。      真正的解析逻辑已经抽到 `app.utils.utils.get_ffmpeg_, _bgm_readiness(), _collector_readiness(), _ffmpeg_readiness(), list_render_blockers(), _provider_checks(), Return actionable blocker messages for preview/render. (+16 more)

### Community 17 - "Community 17"
Cohesion: 0.10
Nodes (17): build_youtube_extra(), cross_post_if_auto_upload(), cross_post_videos(), _format_caption(), get_active_service(), _get_backend(), get_backend_name(), Cross-platform video publishing via Upload-Post or Zernio. (+9 more)

### Community 18 - "Community 18"
Cohesion: 0.09
Nodes (18): font_dir(), get_ffmpeg_binary(), get_response(), normalize_script_for_subtitle_matching(), public_dir(), Any, Resolve subtitle font with bundled and system fallbacks., 解析当前进程应该使用的 FFmpeg 可执行文件。      增加原因：     1. 视频编码、静音音频生成、pydub 音频转码都依赖 FFmpeg； (+10 more)

### Community 19 - "Community 19"
Cohesion: 0.18
Nodes (25): create_audio(), create_subtitle(), create_task(), create_video(), delete_video(), download_video(), get_all_tasks(), get_bgm_list() (+17 more)

### Community 20 - "Community 20"
Cohesion: 0.13
Nodes (16): _apply_niche_to_prompt(), channel_dir(), default_db_path(), load_channel(), load_settings(), _normalize_channel_collections(), Any, Path (+8 more)

### Community 22 - "Community 22"
Cohesion: 0.20
Nodes (22): clear_generation_lock(), ClearLockRequest, get_preview_audio(), get_providers(), get_runtime_limits(), get_workspace(), get_workspace_steps(), _load_channel_runtime_or_404() (+14 more)

### Community 23 - "Community 23"
Cohesion: 0.20
Nodes (6): Connection, Any, Path, _row_to_topic(), TopicStore, Row

### Community 24 - "Community 24"
Cohesion: 0.13
Nodes (18): music_profiles_for_category(), normalize_category(), Editorial categories and music defaults — technical identifiers in English., Map legacy PT category slugs to English; pass through valid EN slugs., topic_distribution_for_channel(), normalize_music_profiles(), Read music_profiles from topic; derive from category when absent., SQLite-backed topic queue for pipeline channels. (+10 more)

### Community 25 - "Community 25"
Cohesion: 0.09
Nodes (6): The rerank rebuild must merge by term dict, not reconstruct with         only we, 自定义音频不会经过 TTS，所以没有 sub_maker。         Whisper 可以直接从音频文件转写，此时不能被 sub_maker 为空的保护逻, Edge 字幕依赖 TTS 返回的 sub_maker 时间轴。         自定义音频缺少该对象时应继续跳过，避免产生不可信的字幕时间轴。, 任务生成入口和 WebUI/API 共用 VideoParams。这里验证自动生成文案时，         高级提示词参数会继续传到 LLM 服务层，避免只在, 默认模式不受影响；只有用户显式开启素材按文案顺序匹配时，任务层才         要求 LLM 生成有序关键词，并适当增加关键词数量以覆盖更多脚本片段。, TestTaskService

### Community 26 - "Community 26"
Cohesion: 0.11
Nodes (22): _channel_header_meta_line(), _collector_job_snapshot(), compute_pipeline_step_states(), _effective_runtime(), _format_summary_value(), _humanize_model_label(), _preview_checklist_state(), Collector stage editor. Returns True if fetch clips requested. (+14 more)

### Community 27 - "Community 27"
Cohesion: 0.21
Nodes (21): _clamp_weight(), _coerce_editor_rows(), count_video_terms(), ensure_video_terms_session_state(), format_for_display(), get_normalized_video_terms(), has_video_terms(), _normalized_from_rows() (+13 more)

### Community 28 - "Community 28"
Cohesion: 0.13
Nodes (15): ChannelConfigResponse, channelsApi, ChannelSummary, Topic, channelsStore, workspaceStore, State, useChannelsStore (+7 more)

### Community 29 - "Community 29"
Cohesion: 0.16
Nodes (21): chatterbox_tts(), _configure_pydub_ffmpeg(), elevenlabs_tts(), ensure_legacy_submaker_fields(), gemini_tts(), get_audio_duration(), _get_audio_duration_from_mp3(), _get_audio_duration_from_submaker() (+13 more)

### Community 30 - "Community 30"
Cohesion: 0.12
Nodes (19): _build_elevenlabs_premade_voices(), get_all_azure_voices(), get_chatterbox_voices(), _get_elevenlabs_api_key(), get_elevenlabs_voices(), get_elevenlabs_voices_list_mode(), get_gemini_voices(), get_mimo_voices() (+11 more)

### Community 31 - "Community 31"
Cohesion: 0.18
Nodes (18): count_by_status(), find_topic(), get_next_pending(), load_topics(), mark_approved(), mark_failed(), mark_generated(), mark_processing() (+10 more)

### Community 33 - "Community 33"
Cohesion: 0.10
Nodes (19): dependencies, pinia, vue, vue-router, devDependencies, @types/node, typescript, vite (+11 more)

### Community 34 - "Community 34"
Cohesion: 0.13
Nodes (11): api, ApiError, Envelope, configApi, ConfigPatch, ConfigSnapshot, llmApi, config (+3 more)

### Community 35 - "Community 35"
Cohesion: 0.16
Nodes (6): TaskQueueFullError, InMemoryTaskManager, _FakeRequest, endpoint 未显式配置时，任务查询接口不能使用 Host 派生绝对 URL，         也不能把展示 URL 回写到任务状态里，否则不同 Host, 并发数用尽后，等待队列必须有硬上限。这里用 max_concurrent_tasks=0         强制任务进入队列，验证超过 max_queued_ta, TestSecurityControls

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (16): ProviderReadiness, ProvidersResponse, WorkspaceSteps, State, StepId, StepState, WorkspaceBgm, WorkspaceMedia (+8 more)

### Community 37 - "Community 37"
Cohesion: 0.14
Nodes (8): apply_section_patch(), is_secret_field(), mask_section(), mask_value(), Any, Secret masking for the cockpit's Config endpoint.  config.toml holds live provid, Merge `patch` into the live `section` dict, in place.      Skips any secret fiel, TestConfigMasking

### Community 38 - "Community 38"
Cohesion: 0.14
Nodes (14): TaskState, videosApi, errorMessage, router, submitting, workspaceStore, isDone, poll() (+6 more)

### Community 39 - "Community 39"
Cohesion: 0.12
Nodes (8): 按文案顺序匹配素材依赖 LLM 返回有序关键词。这里不调用真实模型，         只验证服务层会把"按脚本叙事顺序输出"的约束写入 prompt，避免, terms_output_mode="simple" is the escape hatch for weaker LLMs: no         visua, reasoning 模型可能返回 `<think>...</think>`。脚本生成链路必须只保留         最终正文，避免思考过程进入字幕和配音。, 如果模型只返回思考块而没有最终答案，应视为空内容，触发重试或明确错误。, 某些网关可能因为截断只返回未闭合的 `<think>`。这种内容同样不能         进入最终脚本；如果清理后没有正文，就应该按空响应处理。, 高级文案要求只作为附加约束，不替换默认系统提示词。         这样普通用户不配置时仍然走稳定默认规则，高级用户也能细化风格。, 自定义 system prompt 会替换默认脚本规则，但视频主题、语言、段落数         仍由服务层统一追加，避免高级用户漏写必要上下文。, TestScriptPromptOptions

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (4): language 默认 auto 时，不应该固定成某个国家或语种，而是让模型         跟随视频主题和脚本的语言，扩大 API 适用范围。, 外部 API 不能接受无限长的脚本和语言参数，否则会直接放大 LLM         token 成本。schema 层先拦截，服务层再做内部调用兜底。, TestSocialMetadata, VideoSocialMetadataRequest

### Community 41 - "Community 41"
Cohesion: 0.12
Nodes (12): errorMessage, includeAudio, workspaceStore, props, router, stepLabels, steps, workspaceStore (+4 more)

### Community 42 - "Community 42"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 43 - "Community 43"
Cohesion: 0.27
Nodes (15): build_video_payload(), cmd_approve(), cmd_dry_run(), cmd_generate(), cmd_publish(), cmd_retry(), cmd_stats(), _first_or_none() (+7 more)

### Community 44 - "Community 44"
Cohesion: 0.12
Nodes (8): Coverr 视频素材源(spec: 2026-06-09-coverr-video-provider-design.md)。     全部用 unittest, search_videos_coverr 应把每个 hit 转成 MaterialInfo，并把 urls.mp4_download         直接作为, 与 pexels/pixabay 一致:未显式配置时 TLS 校验默认开启。, 企业自签证书代理场景必须能显式关闭 TLS 校验。, Coverr duration 字段在不同响应里可能是 number 或 string,         两种格式都要接受;低于 minimum_duratio, 缺 id 或缺 urls.mp4_download 的条目应被跳过,不应抛异常。, 响应结构异常 / 网络异常时,函数必须返回 [] 而不是抛异常,         与 pexels/pixabay 行为保持一致。, TestCoverrProvider

### Community 45 - "Community 45"
Cohesion: 0.17
Nodes (16): apply_channel_defaults(), apply_runtime_config(), build_runtime_config(), handle_channel_selection(), _init_cockpit_session_state(), Build a flat runtime snapshot from channel.json for form comparison., Apply channel runtime snapshot to session state and config.ui., Load channel.json defaults into Streamlit session state and config.ui. (+8 more)

### Community 46 - "Community 46"
Cohesion: 0.15
Nodes (16): _apply_publish_mode(), maybe_auto_publish_after_render(), _publish_auto_upload_key(), _publish_readiness(), Resolve publish targets from channel publish_profiles or global config., Map session/config to publish mode: manual | auto | skip., Single mutually-exclusive control for how publishing runs after render., Publish step editor. Returns True if publish was requested. (+8 more)

### Community 47 - "Community 47"
Cohesion: 0.16
Nodes (9): exception_handler(), get_application(), Request, Application implementation - ASGI., Initialize FastAPI application.      Returns:        FastAPI: Application object, validation_exception_handler(), Application configuration - root APIRouter.  Defines all FastAPI application end, RequestValidationError (+1 more)

### Community 48 - "Community 48"
Cohesion: 0.16
Nodes (15): _build_subtitle_formatter(), _build_subtitle_items_from_edge_cues(), _build_subtitle_items_from_legacy_submaker(), create_subtitle(), _do(), _format_text(), _match_script_line(), _normalize_arabic() (+7 more)

### Community 49 - "Community 49"
Cohesion: 0.13
Nodes (15): estimate_no_voice_duration(), get_elevenlabs_fallback_voice(), is_chatterbox_voice(), is_elevenlabs_voice(), is_gemini_voice(), is_mimo_voice(), is_no_voice(), is_siliconflow_voice() (+7 more)

### Community 50 - "Community 50"
Cohesion: 0.22
Nodes (9): i18nApi, KNOWN_LOCALES, LocaleCode, LocaleFile, uiStore, tabs, uiStore, State (+1 more)

### Community 51 - "Community 51"
Cohesion: 0.20
Nodes (10): extract_task_id_from_path(), Any, Path, Detect and persist silent BGM mixing failures (VisualAI spec 011)., read_bgm_failure(), record_bgm_failure(), sidecar_path(), _utc_now_iso() (+2 more)

### Community 52 - "Community 52"
Cohesion: 0.14
Nodes (14): azure_tts_v1(), azure_tts_v2(), convert_rate_to_percent(), create_edge_tts_communicate(), get_edge_tts_timeout_seconds(), is_azure_v2_voice(), parse_voice_name(), 按当前已安装的 edge_tts 版本构造 Communicate 对象。      背景：     1. 主线代码已经升级到 edge_tts 7.x，并使用 (+6 more)

### Community 54 - "Community 54"
Cohesion: 0.14
Nodes (3): 兼容 PR #981 曾使用过的 none sentinel，避免少量直接调用 API 的用户         升级后立即失效。新 UI 和新代码仍统一使用 n, Success path: POST /audio/speech, write audio, return legacy SubMaker., TestVoiceService

### Community 55 - "Community 55"
Cohesion: 0.22
Nodes (10): _can_resolve_hostname(), _decode_linux_route_gateway(), get_container_default_gateway_ip(), get_default_ollama_base_url(), is_running_in_container(), load_config(), 返回 Ollama 的默认 OpenAI-compatible base_url。      用户显式配置 `ollama_base_url` 时不会走这里；这, 判断当前进程是否运行在容器内。      这个判断主要用于 Ollama 默认地址选择：     - 普通本机运行时，`localhost` 指向用户机器本身； (+2 more)

### Community 58 - "Community 58"
Cohesion: 0.18
Nodes (9): collectorApi, errorMessage, fetchClips(), fetching, jobStatus, lastJob, pollJob(), workspaceStore (+1 more)

### Community 59 - "Community 59"
Cohesion: 0.18
Nodes (9): publishApi, PublishStatus, errorMessage, publishing, results, selectedPlatforms, status, videoPaths (+1 more)

### Community 60 - "Community 60"
Cohesion: 0.36
Nodes (11): allowed_bgm_directories(), list_profiles(), list_tracks(), pick_random_track(), profile_music_dir(), Path, resolve_bgm(), _resolve_explicit_bgm_file() (+3 more)

### Community 61 - "Community 61"
Cohesion: 0.26
Nodes (7): Mode 5 — faceless stock-footage automation defaults., apply_mode_defaults(), pick_mode(), Any, Mode registry for editorial defaults (VisualAI spec 015, trimmed for MPT)., supported_modes(), TestModesRegistry

### Community 62 - "Community 62"
Cohesion: 0.20
Nodes (8): _match_labeled_paragraph(), parse_script_scenes(), Any, Lightweight script scene splitter for intro/body/CTA editorial flows., Split a script into editorial scenes without LLM calls., _split_paragraphs(), TestSceneParser, render_scene_breakdown()

### Community 63 - "Community 63"
Cohesion: 0.26
Nodes (6): Exception, ApiClient, ApiError, Any, Response, HTTP client for MoneyPrinterTurbo API (no API keys — uses server config.toml).

### Community 64 - "Community 64"
Cohesion: 0.17
Nodes (3): 普通 Linux 也有 /proc/1/cgroup，不能因为文件存在就判定为容器。, TestLiteLLMLiveIntegration, TestRuntimeEnvironmentDetection

### Community 66 - "Community 66"
Cohesion: 0.42
Nodes (11): InspectorCallbacks, Any, Stage-specific configuration inspector for the production cockpit., Render configuration controls for the active pipeline step., render_inspector_media(), render_inspector_publish(), render_inspector_result(), render_inspector_script() (+3 more)

### Community 67 - "Community 67"
Cohesion: 0.17
Nodes (12): _preview_checklist_html(), Render step editor — returns whether render was requested., Action row for result artifact cards., Result step — artifact cards with actions., Document-style stage header for the main editor column., Preview gate editor. Returns (preview_btn, include_audio, skip_preview)., render_document_divider(), render_document_stage() (+4 more)

### Community 68 - "Community 68"
Cohesion: 0.20
Nodes (7): errorMessage, generateScript(), generateTerms(), generatingScript, generatingTerms, workspaceStore, ws()

### Community 69 - "Community 69"
Cohesion: 0.47
Nodes (10): get_channel(), list_channels(), list_topics(), _load_channel_or_404(), load_topic_into_workspace(), BaseModel, Request, _topic_store() (+2 more)

### Community 70 - "Community 70"
Cohesion: 0.29
Nodes (10): collector_dashboard(), collector_health(), collector_search(), create_collector_job(), CreateCollectorJobRequest, get_collector_job(), BaseModel, Request (+2 more)

### Community 71 - "Community 71"
Cohesion: 0.18
Nodes (4): download_videos 可能被服务层或测试直接传入字符串模式，而不是         VideoConcatMode 枚举。这里用空搜索词避免真实网络请, 默认路径必须开启 TLS 校验，避免素材 API key 和返回的素材 URL         在公共网络或不可信代理环境中被中间人攻击截获或篡改。, 少数企业代理会使用自签证书。该场景必须显式配置关闭 TLS 校验，         不能再由代码硬编码默认关闭。, TestMaterialTlsVerification

### Community 72 - "Community 72"
Cohesion: 0.24
Nodes (9): cockpitApi, RuntimeLimits, clearLock(), handleVisibilityChange(), refreshRuntimeLimits(), refreshTasks(), removeTask(), runtimeLimits (+1 more)

### Community 73 - "Community 73"
Cohesion: 0.18
Nodes (10): compilerOptions, allowArbitraryExtensions, erasableSyntaxOnly, noFallthroughCasesInSwitch, noUnusedLocals, noUnusedParameters, tsBuildInfoFile, types (+2 more)

### Community 74 - "Community 74"
Cohesion: 0.24
Nodes (8): normalized_to_workspace_keywords(), NormalizedCollectorKeywords, Server-side keyword helpers for the cockpit API.  Distinct from webui/cockpit_ke, _is_terms_error(), Any, Cockpit preview: generate script + terms (+ optional TTS sample) inline.  Port o, run_preview(), WorkspaceKeywords

### Community 78 - "Community 78"
Cohesion: 0.31
Nodes (3): _load_translation(), TestWebuiI18n, _TrKeyVisitor

### Community 79 - "Community 79"
Cohesion: 0.22
Nodes (10): collect_form_state(), Read tracked form values from session_state and config.ui., Subtitle settings — compact mode shows position + size only., Clickable option cards (VisualAI-style) backed by session state., refresh_channel_overrides(), render_inheritance_badge(), render_option_cards(), render_subtitle_controls() (+2 more)

### Community 80 - "Community 80"
Cohesion: 0.31
Nodes (8): list_music(), music_path_for_api(), pick_music_profile(), pick_random_music(), Path, Pipeline music library — profiles under pipeline/assets/music/., Pick profile from topic pool; honors optional preferred_music when set., Relative path from project root for MoneyPrinterTurbo BGM resolution.

### Community 85 - "Community 85"
Cohesion: 0.25
Nodes (4): Whisper fallback 校正阶段也必须忽略 `---` 这类不可发声脚本行。          如果这里继续保留 Markdown 分隔符，`corr, The final subtitle must be parsed even when the SRT file does not end         wi, A normal SRT ending in a blank line still parses all blocks., TestSubtitleService

### Community 92 - "Community 92"
Cohesion: 0.53
Nodes (4): correct(), file_to_subtitles(), levenshtein_distance(), similarity()

### Community 93 - "Community 93"
Cohesion: 0.53
Nodes (5): fadein_transition(), fadeout_transition(), slidein_transition(), slideout_transition(), Clip

### Community 94 - "Community 94"
Cohesion: 0.33
Nodes (6): ensure_file_path_exists(), generate_silent_audio(), 将已经聚合好的字幕段写入到 SRT 文件，并做一次基本可读性验证。      返回值：     - `True`：字幕文件成功落盘且可被 moviepy 解析；, 生成 MP3 静音音频，作为“无配音”模式的时间轴占位。      使用 FFmpeg 的 anullsrc 直接生成静音，比先构造临时 WAV 再转码更少中间, 确保输出文件所在目录一定存在。      这里单独做一层兜底，是因为 edge_tts 7.x 在真正发起网络请求之前，     就会先打开目标音频文件；如果目, _write_subtitle_items()

### Community 96 - "Community 96"
Cohesion: 0.33
Nodes (3): MaterialInfo, 开启按文案顺序匹配素材后，不能让第一个关键词的多个候选先把         音频时长填满。这里模拟两个关键词各有多个候选，验证下载顺序是         ter, 在 source="coverr" 时:           1. dispatch 到 search_videos_coverr           2. c

### Community 97 - "Community 97"
Cohesion: 0.40
Nodes (3): app, router, STEP_IDS

### Community 98 - "Community 98"
Cohesion: 0.80
Nodes (4): get_api_key(), get_task_id(), Request, verify_token()

### Community 99 - "Community 99"
Cohesion: 0.50
Nodes (3): _friendly_name(), list_voices(), TTS voice listing for the cockpit API.  Port of the per-provider voice-listing l

### Community 102 - "Community 102"
Cohesion: 0.50
Nodes (4): Compact sidebar summary of inherited channel settings., Montagem step — checklist, settings summary and script preview., render_assembly_panel(), render_channel_summary()

### Community 141 - "Community 141"
Cohesion: 0.25
Nodes (7): generate_video_script(), generate_video_social_metadata(), generate_video_terms(), Request, API 请求模型需要限制高级 prompt 参数，避免外部调用绕过 WebUI         传入异常段落数或超长提示词，导致模型成本和结果不可控。, VideoScriptRequest, VideoTermsRequest

## Ambiguous Edges - Review These
- `docker-compose.yml` → `Dockerfile.gpu (CUDA base image)`  [AMBIGUOUS]
  docker-compose.yml · relation: references

## Knowledge Gaps
- **117 isolated node(s):** `moneyprinterturbo`, `build_webui.sh script`, `name`, `private`, `version` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **51 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `docker-compose.yml` and `Dockerfile.gpu (CUDA base image)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **Why does `Workspace` connect `Community 4` to `Community 74`, `Community 28`, `Community 36`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `TestVoiceService` connect `Community 54` to `Community 128`, `Community 129`, `Community 130`, `Community 53`, `Community 112`, `Community 113`, `Community 114`, `Community 115`, `Community 116`, `Community 117`, `Community 118`, `Community 119`, `Community 120`, `Community 121`, `Community 122`, `Community 123`, `Community 124`, `Community 125`, `Community 126`, `Community 127`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `CollectorSelectedClip` connect `Community 3` to `Community 1`, `Community 36`, `Community 5`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 63 inferred relationships involving `tr()` (e.g. with `_bgm_readiness()` and `_collector_readiness()`) actually correct?**
  _`tr()` has 63 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `TopicStore` (e.g. with `_topic_store()` and `TopicStatusUpdate`) actually correct?**
  _`TopicStore` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Application implementation - ASGI.`, `Initialize FastAPI application.      Returns:        FastAPI: Application object`, `判断当前进程是否运行在容器内。      这个判断主要用于 Ollama 默认地址选择：     - 普通本机运行时，`localhost` 指向用户机器本身；` to the rest of the system?**
  _420 weakly-connected nodes found - possible documentation gaps or missing edges._