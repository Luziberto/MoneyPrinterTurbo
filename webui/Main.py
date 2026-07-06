import os
import sys
import webbrowser
from uuid import UUID, uuid4

import requests
import streamlit as st
from loguru import logger

# Add the root directory of the project to the system path to allow importing modules from the project
root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)
    print("******** sys.path ********")
    print(sys.path)
    print("")

from app.config import config
from app.models.schema import (
    MaterialInfo,
    NormalizedCollectorKeywords,
    VideoAspect,
    VideoConcatMode,
    VideoParams,
    VideoTransitionMode,
    format_collector_keywords_for_ui,
)
from app.services import bgm as bgm_service
from app.services import llm, voice
from app.services import task as tm
from app.services.runtime_limits import (
    GenerationAlreadyRunningError,
    generation_lock_status,
    single_flight_generation_lock,
)
from app.utils import utils
from webui import cockpit as _cockpit_module
from webui.cockpit_inspector import InspectorCallbacks

import importlib

# Streamlit keeps module objects across reruns; reload so UI changes apply without
# restarting the server (and recover from a partially stale cockpit import).
cockpit = importlib.reload(_cockpit_module)


def _format_generated_terms(terms: NormalizedCollectorKeywords | str) -> str:
    if isinstance(terms, NormalizedCollectorKeywords):
        return format_collector_keywords_for_ui(
            [keyword.model_dump() for keyword in terms.keywords]
        )
    return str(terms)


def _is_terms_error(terms: NormalizedCollectorKeywords | str) -> bool:
    return isinstance(terms, str) and "Error: " in terms


st.set_page_config(
    page_title="MoneyPrinterTurbo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "Report a bug": "https://github.com/harry0703/MoneyPrinterTurbo/issues",
        "About": "# MoneyPrinterTurbo\nSimply provide a topic or keyword for a video, and it will "
        "automatically generate the video copy, video materials, video subtitles, "
        "and video background music before synthesizing a high-definition short "
        "video.\n\nhttps://github.com/harry0703/MoneyPrinterTurbo",
    },
)


streamlit_style = """
<style>
h1 {
    padding-top: 0 !important;
}
</style>
"""
st.markdown(streamlit_style, unsafe_allow_html=True)
st.markdown(cockpit.COCKPIT_CSS, unsafe_allow_html=True)

# 定义资源目录
font_dir = os.path.join(root_dir, "resource", "fonts")
song_dir = os.path.join(root_dir, "resource", "songs")
i18n_dir = os.path.join(root_dir, "webui", "i18n")
config_file = os.path.join(root_dir, "webui", ".streamlit", "webui.toml")
system_locale = utils.get_system_locale()
DEFAULT_CHATTERBOX_BASE_URL = "http://127.0.0.1:4123/v1"
DEFAULT_CHATTERBOX_MODEL = "chatterbox"
DEFAULT_CHATTERBOX_VOICES = ["default-Female"]


def _parse_chatterbox_voices(voices):
    # Chatterbox 是自托管服务，音色列表由用户在 WebUI 中手动输入。
    # 这里统一兼容 TOML 数组和输入框里的逗号分隔字符串，避免下拉框、
    # 试听按钮和后续生成流程使用不同格式导致状态不一致。
    if isinstance(voices, str):
        return [v.strip() for v in voices.split(",") if v.strip()]
    return [str(v).strip() for v in voices or [] if str(v).strip()]


def _sync_chatterbox_config_from_session_state():
    # Streamlit 的按钮会触发整页 rerun，而 Chatterbox 配置输入框位于
    # “试听语音合成”按钮之后。如果试听时只读取 config.chatterbox，可能拿不到
    # 用户刚在输入框里填入的 base_url/model/voices。先从 session_state 同步一次，
    # 可以保证按钮逻辑和输入框显示逻辑使用同一份最新配置。
    config.chatterbox["base_url"] = (
        st.session_state.get(
            "chatterbox_base_url_input",
            config.chatterbox.get("base_url") or DEFAULT_CHATTERBOX_BASE_URL,
        )
        or ""
    ).strip()
    config.chatterbox["api_key"] = st.session_state.get(
        "chatterbox_api_key_input", config.chatterbox.get("api_key", "")
    )
    config.chatterbox["model_id"] = (
        st.session_state.get(
            "chatterbox_model_input",
            config.chatterbox.get("model_id") or DEFAULT_CHATTERBOX_MODEL,
        )
        or DEFAULT_CHATTERBOX_MODEL
    ).strip()
    config.chatterbox["voices"] = _parse_chatterbox_voices(
        st.session_state.get(
            "chatterbox_voices_input",
            config.chatterbox.get("voices") or DEFAULT_CHATTERBOX_VOICES,
        )
    )


def _detect_audio_mime(audio_file: str, audio_bytes: bytes) -> str:
    # 有些 OpenAI-compatible TTS 服务，例如 travisvn/chatterbox-tts-api，
    # 即使请求 response_format=mp3，也会返回 WAV 内容。WebUI 试听如果固定
    # 使用 audio/mp3，浏览器可能无法播放，因此这里按文件头识别真实格式。
    header = audio_bytes[:12]
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "audio/wav"
    if header.startswith(b"ID3") or header[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mp3"
    if header.startswith(b"OggS"):
        return "audio/ogg"
    ext = os.path.splitext(audio_file)[1].lower()
    return {
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }.get(ext, "audio/mp3")


if "video_subject" not in st.session_state:
    st.session_state["video_subject"] = ""
if "video_script" not in st.session_state:
    st.session_state["video_script"] = ""
if "video_terms" not in st.session_state:
    st.session_state["video_terms"] = ""
if "video_script_prompt" not in st.session_state:
    st.session_state["video_script_prompt"] = ""
if "custom_system_prompt" not in st.session_state:
    st.session_state["custom_system_prompt"] = llm.DEFAULT_SCRIPT_SYSTEM_PROMPT
if "use_custom_system_prompt" not in st.session_state:
    st.session_state["use_custom_system_prompt"] = False
if "match_materials_to_script" not in st.session_state:
    st.session_state["match_materials_to_script"] = bool(
        config.app.get("match_materials_to_script", False)
    )
if "ui_language" not in st.session_state:
    st.session_state["ui_language"] = config.ui.get("language", system_locale)
if "local_video_materials" not in st.session_state:
    # 记住用户最近一次已经落盘的本地素材，避免仅修改文案后二次生成时丢失素材列表。
    st.session_state["local_video_materials"] = []
if "active_channel" not in st.session_state:
    st.session_state["active_channel"] = config.ui.get("active_channel", "")
if "preview_ready" not in st.session_state:
    st.session_state["preview_ready"] = False
if "cockpit_skip_preview" not in st.session_state:
    st.session_state["cockpit_skip_preview"] = False

# 加载语言文件
locales = utils.load_locales(i18n_dir)

# 创建一个顶部栏，包含标题和语言选择
title_col, lang_col = st.columns([4, 1])

with title_col:
    st.markdown(
        '<div class="cockpit-app-header">'
        f'<span class="cockpit-app-brand">MoneyPrinterTurbo</span>'
        f'<span class="cockpit-app-version">v{config.project_version}</span>'
        "</div>",
        unsafe_allow_html=True,
    )

with lang_col:
    display_languages = []
    selected_index = 0
    for i, code in enumerate(locales.keys()):
        display_languages.append(f"{code} - {locales[code].get('Language')}")
        if code == st.session_state.get("ui_language", ""):
            selected_index = i

    selected_language = st.selectbox(
        "Language / 语言",
        options=display_languages,
        index=selected_index,
        key="top_language_selector",
        label_visibility="collapsed",
    )
    if selected_language:
        code = selected_language.split(" - ")[0].strip()
        st.session_state["ui_language"] = code
        config.ui["language"] = code

support_locales = [
    "zh-CN",
    "zh-HK",
    "zh-TW",
    "de-DE",
    "en-US",
    "fr-FR",
    "ru-RU",
    "vi-VN",
    "th-TH",
    "tr-TR",
]


def get_all_fonts():
    fonts = []
    for root, dirs, files in os.walk(font_dir):
        for file in files:
            if file.endswith(".ttf") or file.endswith(".ttc"):
                fonts.append(file)
    fonts.sort()
    return fonts


def get_all_songs():
    songs = []
    for root, dirs, files in os.walk(song_dir):
        for file in files:
            if file.endswith(".mp3"):
                songs.append(file)
    return songs


def open_task_folder(task_id):
    try:
        # task_id 应始终是服务端生成的 UUID。这里先做格式校验，避免异常值
        # 通过路径拼接访问任务目录之外的位置，也避免后续打开目录时触发
        # 平台 shell 对特殊字符的解释。
        normalized_task_id = str(UUID(str(task_id)))
        tasks_root = os.path.abspath(os.path.join(root_dir, "storage", "tasks"))
        path = os.path.abspath(os.path.join(tasks_root, normalized_task_id))

        # 即使 UUID 校验通过，也再次确认最终路径仍在任务根目录内，避免
        # 未来调用方调整 task_id 来源时引入路径穿越风险。
        if not path.startswith(tasks_root + os.sep):
            logger.warning(f"invalid task folder path: {path}")
            return

        if os.path.isdir(path):
            webbrowser.open(f"file://{path}")
    except Exception as e:
        logger.error(e)


def scroll_to_bottom():
    js = """
    <script>
        console.log("scroll_to_bottom");
        function scroll(dummy_var_to_force_repeat_execution){
            var sections = parent.document.querySelectorAll('section.main');
            console.log(sections);
            for(let index = 0; index<sections.length; index++) {
                sections[index].scrollTop = sections[index].scrollHeight;
            }
        }
        scroll(1);
    </script>
    """
    st.components.v1.html(js, height=0, width=0)


def init_log():
    logger.remove()
    _lvl = "DEBUG"

    def format_record(record):
        # 获取日志记录中的文件全路径
        file_path = record["file"].path
        # 将绝对路径转换为相对于项目根目录的路径
        relative_path = os.path.relpath(file_path, root_dir)
        # 更新记录中的文件路径
        record["file"].path = f"./{relative_path}"
        # 返回修改后的格式字符串
        # 您可以根据需要调整这里的格式
        record["message"] = record["message"].replace(root_dir, ".")

        _format = (
            "<green>{time:%Y-%m-%d %H:%M:%S}</> | "
            + "<level>{level}</> | "
            + '"{file.path}:{line}":<blue> {function}</> '
            + "- <level>{message}</>"
            + "\n"
        )
        return _format

    logger.add(
        sys.stdout,
        level=_lvl,
        format=format_record,
        colorize=True,
    )


init_log()

locales = utils.load_locales(i18n_dir)


def tr(key):
    loc = locales.get(st.session_state["ui_language"], {})
    return loc.get("Translation", {}).get(key, key)

@st.cache_data(ttl=300, show_spinner=False)
def get_groq_model_ids(api_key: str, base_url: str) -> list[str]:
    if not api_key:
        return []

    normalized_base_url = (base_url or "https://api.groq.com/openai/v1").strip().rstrip("/")
    models_url = f"{normalized_base_url}/models"

    try:
        response = requests.get(
            models_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])

        model_ids = []
        for item in data:
            if isinstance(item, dict):
                model_id = item.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    model_ids.append(model_id.strip())

        return sorted(set(model_ids))
    except Exception as e:
        logger.warning(f"failed to fetch groq models: {e}")
        return []

_available_channels = cockpit.list_available_channels()
_active_channel_slug = cockpit.render_channel_toolbar(_available_channels, tr)

tab_create, tab_channels, tab_tasks, tab_config = st.tabs(
    [
        tr("Cockpit Tab Create"),
        tr("Cockpit Tab Channels"),
        tr("Cockpit Tab Tasks"),
        tr("Cockpit Tab Config"),
    ]
)

with tab_channels:
    cockpit.render_channels_tab(_available_channels, tr)

with tab_tasks:
    tasks_root = os.path.join(root_dir, "storage", "tasks")
    cockpit.render_tasks_tab(tasks_root, tr, open_task_folder)

with tab_config:
    if config.app.get("hide_config", False):
        st.info(tr("Cockpit Config Hidden"))
    else:
        config_panels = st.columns(3)
        left_config_panel = config_panels[0]
        middle_config_panel = config_panels[1]
        right_config_panel = config_panels[2]

        # 左侧面板 - 日志设置
        with left_config_panel:
            # 是否隐藏配置面板
            hide_config = st.checkbox(
                tr("Hide Basic Settings"), value=config.app.get("hide_config", False)
            )
            config.app["hide_config"] = hide_config

            # 是否禁用日志显示
            hide_log = st.checkbox(
                tr("Hide Log"), value=config.ui.get("hide_log", False)
            )
            config.ui["hide_log"] = hide_log

        # 中间面板 - LLM 设置

        with middle_config_panel:
            st.write(tr("LLM Settings"))
            # 下拉框展示文本和后端 provider id 分开维护，避免 UI 文案变化
            # 污染 `config.app["llm_provider"]` 这类稳定配置值。
            llm_provider_options = [
                ("OpenAI", "openai"),
                ("AIHubMix", "aihubmix"),
                ("AIML API", "aimlapi"),
                ("EvoLink", "evolink"),
                ("VolcEngine", "volcengine"),
                ("Moonshot", "moonshot"),
                ("Azure", "azure"),
                ("Qwen", "qwen"),
                ("DeepSeek", "deepseek"),
                ("ModelScope", "modelscope"),
                ("Gemini", "gemini"),
                ("Anthropic", "anthropic"),
                ("Grok", "grok"),
                ("Groq", "groq"),
                ("Ollama", "ollama"),
                ("G4f", "g4f"),
                ("OneAPI", "oneapi"),
                ("Cloudflare", "cloudflare"),
                ("ERNIE", "ernie"),
                ("MiniMax", "minimax"),
                ("MiMo", "mimo"),
                ("Pollinations", "pollinations"),
                ("AWS Bedrock", "bedrock"),
                ("LiteLLM", "litellm"),
            ]
            llm_provider_ids = [provider_id for _, provider_id in llm_provider_options]
            llm_provider_labels = {
                provider_id: label for label, provider_id in llm_provider_options
            }
            saved_llm_provider = config.app.get("llm_provider", "openai").lower()
            if saved_llm_provider not in llm_provider_ids:
                saved_llm_provider = "openai"

            # Streamlit 会把没有 key 的 selectbox 视为一个由 label/options/index
            # 共同决定的临时控件。如果每次选择后都根据 config.app 重新计算 index，
            # 用户第一次切换 provider 后控件可能被重建，表现为“必须选择两次才生效”。
            # 这里用稳定的 provider id 作为真实选项，并给控件固定 key；展示文案只
            # 通过 format_func 转换，避免 UI 文案变化影响状态。
            if st.session_state.get("llm_provider_select") not in (
                None,
                *llm_provider_ids,
            ):
                del st.session_state["llm_provider_select"]

            llm_provider = st.selectbox(
                tr("LLM Provider"),
                options=llm_provider_ids,
                index=llm_provider_ids.index(saved_llm_provider),
                format_func=lambda provider_id: llm_provider_labels[provider_id],
                key="llm_provider_select",
            )
            llm_helper = st.container()
            config.app["llm_provider"] = llm_provider

            llm_api_key = config.app.get(f"{llm_provider}_api_key", "")
            llm_secret_key = config.app.get(
                f"{llm_provider}_secret_key", ""
            )  # only for baidu ernie
            llm_base_url = config.app.get(f"{llm_provider}_base_url", "")
            llm_model_name = config.app.get(f"{llm_provider}_model_name", "")
            llm_account_id = config.app.get(f"{llm_provider}_account_id", "")

            tips = ""
            if llm_provider == "ollama":
                if not llm_model_name:
                    llm_model_name = "qwen:7b"
                if not llm_base_url:
                    llm_base_url = config.get_default_ollama_base_url()

                with llm_helper:
                    docker_hint = ""
                    if config.is_running_in_container():
                        docker_hint = "\n                            > 检测到容器环境，未配置 Base Url 时会默认使用 `http://host.docker.internal:11434/v1`\n"
                    tips = f"""
                            ##### Ollama配置说明
                            - **API Key**: 随便填写，比如 123
                            - **Base Url**: 一般为 http://localhost:11434/v1
                                - 如果 `MoneyPrinterTurbo` 和 `Ollama` **不在同一台机器上**，需要填写 `Ollama` 机器的IP地址
                                - 如果 `MoneyPrinterTurbo` 是 `Docker` 部署，建议填写 `http://host.docker.internal:11434/v1`{docker_hint}
                            - **Model Name**: 使用 `ollama list` 查看，比如 `qwen:7b`
                            """

            if llm_provider == "openai":
                if not llm_model_name:
                    llm_model_name = "gpt-3.5-turbo"
                with llm_helper:
                    tips = """
                            ##### OpenAI 配置说明
                            > 需要VPN开启全局流量模式
                            - **API Key**: [点击到官网申请](https://platform.openai.com/api-keys)
                            - **Base Url**: 官方 OpenAI 可留空；如果使用 OpenAI 兼容供应商（例如 OpenRouter），请填写对应的兼容接口地址
                            - **Model Name**: 填写**有权限**的模型；如果使用兼容供应商，请填写该平台支持的模型 ID
                            """

            if llm_provider == "aihubmix":
                if not llm_model_name:
                    llm_model_name = "gpt-5.4-mini"
                if not llm_base_url:
                    llm_base_url = "https://aihubmix.com/v1"
                with llm_helper:
                    tips = """
                            ##### AIHubMix 配置说明
                            - **API Key**: 在 AIHubMix 控制台创建 API Key
                            - **Base Url**: 预填 https://aihubmix.com/v1
                            - **Model Name**: 默认 gpt-5.4-mini，也可以填写 AIHubMix 支持的其它模型 ID
                            """

            if llm_provider == "aimlapi":
                if not llm_model_name:
                    llm_model_name = "openai/gpt-4o-mini"
                if not llm_base_url:
                    llm_base_url = "https://api.aimlapi.com/v1"
                with llm_helper:
                    tips = """
                            ##### AIML API Configuration
                            - **API Key**: create one at https://aimlapi.com/app/keys
                            - **Base Url**: https://api.aimlapi.com/v1
                            - **Model Name**: for example `openai/gpt-4o-mini`, `openai/gpt-4o`, `anthropic/claude-sonnet-4.5`, or `google/gemini-3-flash-preview`
                            """

            if llm_provider == "evolink":
                if not llm_model_name:
                    llm_model_name = "gpt-5.5"
                if not llm_base_url:
                    llm_base_url = "https://direct.evolink.ai/v1"
                with llm_helper:
                    tips = """
                            ##### EvoLink 配置说明
                            - **API Key**: [点击到官网申请](https://evolink.ai/dashboard/keys)
                            - **Base Url**: 默认 https://direct.evolink.ai/v1
                            - **Model Name**: 默认 gpt-5.5，也可以填写 EvoLink 支持的其它模型 ID
                            """

            if llm_provider == "volcengine":
                if not llm_model_name:
                    llm_model_name = "doubao-seed-2-1-turbo-260628"
                if not llm_base_url:
                    llm_base_url = "https://ark.cn-beijing.volces.com/api/v3"
                with llm_helper:
                    tips = """
                            ##### VolcEngine Ark 配置说明
                            - **注册链接**: [点击注册 火山引擎](https://www.volcengine.com/activity/ai618?utm_campaign=hw&utm_content=hw&utm_medium=devrel_tool_web&utm_source=OWO&utm_term=MoneyPrinterTurbo)
                            - **API Key**: 在火山引擎方舟控制台创建 API Key
                            - **Base Url**: 默认 https://ark.cn-beijing.volces.com/api/v3
                            - **Model Name**: 填写 Ark 控制台已开通的模型 ID，例如 doubao-seed-2-1-turbo-260628
                            """

            if llm_provider == "moonshot":
                if not llm_model_name:
                    llm_model_name = "moonshot-v1-8k"
                with llm_helper:
                    tips = """
                            ##### Moonshot 配置说明
                            - **API Key**: [点击到官网申请](https://platform.moonshot.cn/console/api-keys)
                            - **Base Url**: 固定为 https://api.moonshot.cn/v1
                            - **Model Name**: 比如 moonshot-v1-8k，[点击查看模型列表](https://platform.moonshot.cn/docs/intro#%E6%A8%A1%E5%9E%8B%E5%88%97%E8%A1%A8)
                            """
            if llm_provider == "oneapi":
                if not llm_model_name:
                    llm_model_name = (
                        "claude-3-5-sonnet-20240620"  # 默认模型，可以根据需要调整
                    )
                with llm_helper:
                    tips = """
                        ##### OneAPI 配置说明
                        - **API Key**: 填写您的 OneAPI 密钥
                        - **Base Url**: 填写 OneAPI 的基础 URL
                        - **Model Name**: 填写您要使用的模型名称，例如 claude-3-5-sonnet-20240620
                        """

            if llm_provider == "qwen":
                if not llm_model_name:
                    llm_model_name = "qwen-max"
                with llm_helper:
                    tips = """
                            ##### 通义千问Qwen 配置说明
                            - **API Key**: [点击到官网申请](https://dashscope.console.aliyun.com/apiKey)
                            - **Base Url**: 留空
                            - **Model Name**: 比如 qwen-max，[点击查看模型列表](https://help.aliyun.com/zh/dashscope/developer-reference/model-introduction#3ef6d0bcf91wy)
                            """

            if llm_provider == "g4f":
                if not llm_model_name:
                    llm_model_name = "gpt-3.5-turbo"
                with llm_helper:
                    tips = """
                            ##### gpt4free 配置说明
                            > [GitHub开源项目](https://github.com/xtekky/gpt4free)，可以免费使用GPT模型，但是**稳定性较差**
                            - **API Key**: 随便填写，比如 123
                            - **Base Url**: 留空
                            - **Model Name**: 比如 gpt-3.5-turbo，[点击查看模型列表](https://github.com/xtekky/gpt4free/blob/main/g4f/models.py#L308)
                            """
            if llm_provider == "azure":
                with llm_helper:
                    tips = """
                            ##### Azure 配置说明
                            > [点击查看如何部署模型](https://learn.microsoft.com/zh-cn/azure/ai-services/openai/how-to/create-resource)
                            - **API Key**: [点击到Azure后台创建](https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/OpenAI)
                            - **Base Url**: 留空
                            - **Model Name**: 填写你实际的部署名
                            """

            if llm_provider == "gemini":
                if not llm_model_name:
                    llm_model_name = "gemini-1.0-pro"

                with llm_helper:
                    tips = """
                            ##### Gemini 配置说明
                            > 需要VPN开启全局流量模式
                            - **API Key**: [点击到官网申请](https://ai.google.dev/)
                            - **Base Url**: 留空
                            - **Model Name**: 比如 gemini-1.0-pro
                            """

            if llm_provider == "grok":
                if not llm_model_name:
                    llm_model_name = "grok-4.3"
                if not llm_base_url:
                    llm_base_url = "https://api.x.ai/v1"

                with llm_helper:
                    tips = """
                            ##### Grok 配置说明
                            - **API Key**: 填写您的 GrokAPI 密钥
                            - **Base Url**: 填写 GrokAPI 的基础 URL
                            - **Model Name**: 比如 grok-4.3
                            """

            if llm_provider == "groq":
                if not llm_model_name:
                    llm_model_name = "llama-3.3-70b-versatile"
                if not llm_base_url:
                    llm_base_url = "https://api.groq.com/openai/v1"

                with llm_helper:
                    tips = """
                            ##### Groq 配置说明
                            - **API Key**: [点击到官网申请](https://console.groq.com/keys)
                            - **Base Url**: 固定为 https://api.groq.com/openai/v1
                            - **Model Name**: 比如 llama-3.3-70b-versatile
                            """

            if llm_provider == "deepseek":
                if not llm_model_name:
                    llm_model_name = "deepseek-chat"
                if not llm_base_url:
                    llm_base_url = "https://api.deepseek.com"
                with llm_helper:
                    tips = """
                            ##### DeepSeek 配置说明
                            - **API Key**: [点击到官网申请](https://platform.deepseek.com/api_keys)
                            - **Base Url**: 固定为 https://api.deepseek.com
                            - **Model Name**: 固定为 deepseek-chat
                            """

            if llm_provider == "mimo":
                if not llm_model_name:
                    llm_model_name = "mimo-v2.5-pro"
                if not llm_base_url:
                    llm_base_url = "https://api.xiaomimimo.com/v1"
                with llm_helper:
                    tips = """
                            ##### Xiaomi MiMo 配置说明
                            - **API Key**: [点击到官网申请](https://platform.xiaomimimo.com/docs/zh-CN/quick-start/first-api-call)
                            - **Base Url**: 固定为 https://api.xiaomimimo.com/v1
                            - **Model Name**: 默认 mimo-v2.5-pro，也可以按官方文档填写其它可用模型
                            """

            if llm_provider == "modelscope":
                if not llm_model_name:
                    llm_model_name = "Qwen/Qwen3-32B"
                if not llm_base_url:
                    llm_base_url = "https://api-inference.modelscope.cn/v1/"
                with llm_helper:
                    tips = """
                            ##### ModelScope 配置说明
                            - **API Key**: [点击到官网申请](https://modelscope.cn/docs/model-service/API-Inference/intro)
                            - **Base Url**: 固定为 https://api-inference.modelscope.cn/v1/
                            - **Model Name**: 比如 Qwen/Qwen3-32B，[点击查看模型列表](https://modelscope.cn/models?filter=inference_type&page=1)
                            """

            if llm_provider == "ernie":
                with llm_helper:
                    tips = """
                            ##### 百度文心一言 配置说明
                            - **API Key**: [点击到官网申请](https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application)
                            - **Secret Key**: [点击到官网申请](https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application)
                            - **Base Url**: 填写 **请求地址** [点击查看文档](https://cloud.baidu.com/doc/WENXINWORKSHOP/s/jlil56u11#%E8%AF%B7%E6%B1%82%E8%AF%B4%E6%98%8E)
                            """

            if llm_provider == "pollinations":
                if not llm_model_name:
                    llm_model_name = "default"
                with llm_helper:
                    tips = """
                            ##### Pollinations AI Configuration
                            - **API Key**: Optional - Leave empty for public access
                            - **Base Url**: Default is https://text.pollinations.ai/openai
                            - **Model Name**: Use 'openai-fast' or specify a model name
                            """

            if llm_provider == "anthropic":
                if not llm_model_name:
                    llm_model_name = llm.DEFAULT_ANTHROPIC_MODEL
                with llm_helper:
                    tips = """
                            ##### Anthropic (API direta)
                            > [Console Anthropic](https://console.anthropic.com/settings/keys) — chave começa com `sk-ant-...`
                            - **API Key**: cole a chave no campo abaixo
                            - **Model Name**: `claude-sonnet-4-5-20250929` (Sonnet 4.5, recomendado)
                            """

            if llm_provider == "litellm":
                if not llm_model_name:
                    llm_model_name = "openai/gpt-4o-mini"
                with llm_helper:
                    tips = """
                            ##### LiteLLM Configuration
                            > [LiteLLM](https://github.com/BerriAI/litellm) routes to 100+ LLM providers via a unified interface.
                            > Set your provider's API key as an env var: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `AWS_ACCESS_KEY_ID`, etc.
                            - **Model Name**: LiteLLM format — `openai/gpt-4o`, `anthropic/claude-sonnet-4-20250514`, `bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0`, `gemini/gemini-2.5-flash`. See [full provider list](https://docs.litellm.ai/docs/providers)
                            """

            if llm_provider == "bedrock":
                if not llm_model_name:
                    llm_model_name = llm.DEFAULT_BEDROCK_SELECT_MODEL
                with llm_helper:
                    tips = """
                            ##### AWS Bedrock 配置说明
                            > 在 [Bedrock 控制台](https://console.aws.amazon.com/bedrock/) 启用目标模型后再调用。
                            - **Bedrock API Key**: 控制台 **API keys** 生成的 Bearer token（`ABSK...`）
                            - **OpenAI GPT (Mantle)**: `openai.gpt-5.4` / `openai.gpt-5.5` — 区域 `us-east-2`（5.4 也支持 `us-west-2`）。无 `gpt-5.5-mini`，请用 `openai.gpt-5.4`
                            - **Claude 4.5**: inference profile，例如 `global.anthropic.claude-sonnet-4-5-20250929-v1:0`，区域 `us-east-1`
                            - **Model IDs**: [官方列表](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)
                            """

            if tips and config.ui.get("language") in ("zh", "pt", "en"):
                st.info(tips)

            st_llm_api_key = ""
            st_llm_base_url = ""
            if llm_provider == "anthropic":
                st_llm_api_key = st.text_input(
                    tr("Anthropic API Key"),
                    value=config.app.get("anthropic_api_key", ""),
                    type="password",
                    key="anthropic_api_key_input",
                    help=tr("Anthropic API Key Help"),
                )
                if st_llm_api_key:
                    config.app["anthropic_api_key"] = st_llm_api_key
            elif llm_provider == "bedrock":
                bedrock_region = config.app.get("bedrock_region", "us-east-1")
                bedrock_api_key = config.app.get("bedrock_api_key", "")

                st_bedrock_region = st.text_input(
                    tr("AWS Region"),
                    value=bedrock_region or "us-east-1",
                    key="bedrock_region_input",
                )
                st_bedrock_api_key = st.text_input(
                    tr("Bedrock API Key"),
                    value=bedrock_api_key,
                    type="password",
                    key="bedrock_api_key_input",
                    help=tr("Bedrock API Key Help"),
                )
                if st_bedrock_api_key:
                    from app.services.llm import (
                        is_valid_bedrock_bearer_token,
                        looks_like_aws_access_key_id,
                        looks_like_bedrock_iam_username,
                    )

                    if looks_like_bedrock_iam_username(st_bedrock_api_key):
                        st.warning(tr("Bedrock API Key IAM Username Hint"))
                    elif looks_like_aws_access_key_id(st_bedrock_api_key):
                        st.warning(tr("Bedrock API Key IAM Hint"))
                    elif not is_valid_bedrock_bearer_token(st_bedrock_api_key):
                        st.warning(tr("Bedrock API Key Invalid Prefix"))
                if st_bedrock_region:
                    config.app["bedrock_region"] = st_bedrock_region
                if st_bedrock_api_key:
                    config.app["bedrock_api_key"] = st_bedrock_api_key

                with st.expander(tr("Bedrock IAM Credentials"), expanded=False):
                    bedrock_access_key = config.app.get("bedrock_aws_access_key_id", "")
                    bedrock_secret_key = config.app.get(
                        "bedrock_aws_secret_access_key", ""
                    )
                    bedrock_session_token = config.app.get(
                        "bedrock_aws_session_token", ""
                    )
                    st_bedrock_access_key = st.text_input(
                        tr("AWS Access Key ID"),
                        value=bedrock_access_key,
                        type="password",
                        key="bedrock_aws_access_key_id_input",
                    )
                    st_bedrock_secret_key = st.text_input(
                        tr("AWS Secret Access Key"),
                        value=bedrock_secret_key,
                        type="password",
                        key="bedrock_aws_secret_access_key_input",
                    )
                    st_bedrock_session_token = st.text_input(
                        tr("AWS Session Token"),
                        value=bedrock_session_token,
                        type="password",
                        key="bedrock_aws_session_token_input",
                    )
                    if st_bedrock_access_key:
                        config.app["bedrock_aws_access_key_id"] = st_bedrock_access_key
                    if st_bedrock_secret_key:
                        config.app["bedrock_aws_secret_access_key"] = st_bedrock_secret_key
                    if st_bedrock_session_token:
                        config.app["bedrock_aws_session_token"] = st_bedrock_session_token
            else:
                st_llm_api_key = st.text_input(
                    tr("API Key"), value=llm_api_key, type="password"
                )
                st_llm_base_url = st.text_input(tr("Base Url"), value=llm_base_url)
            st_llm_model_name = ""
            if llm_provider != "ernie":
                if llm_provider == "groq":
                    effective_api_key = st_llm_api_key or llm_api_key
                    effective_base_url = st_llm_base_url or llm_base_url
                    groq_models = get_groq_model_ids(
                        api_key=effective_api_key,
                        base_url=effective_base_url,
                    )

                    if groq_models:
                        selected_index = 0
                        if llm_model_name in groq_models:
                            selected_index = groq_models.index(llm_model_name)

                        st_llm_model_name = st.selectbox(
                            tr("Model Name"),
                            options=groq_models,
                            index=selected_index,
                            key="groq_model_name_select",
                        )
                    else:
                        st_llm_model_name = st.text_input(
                            tr("Model Name"),
                            value=llm_model_name,
                            key="groq_model_name_input",
                        )
                        if effective_api_key:
                            st.caption(
                                "Unable to load Groq model list right now. You can still enter a model name manually — note it won't be validated until generation."
                            )
                        else:
                            st.caption(
                                "Add a Groq API key to load available models automatically."
                            )
                elif llm_provider == "anthropic":
                    anthropic_models = list(getattr(llm, "ANTHROPIC_MODEL_OPTIONS", []) or [])
                    if llm_model_name and llm_model_name not in anthropic_models:
                        anthropic_models.insert(0, llm_model_name)
                    selected_index = 0
                    if llm_model_name in anthropic_models:
                        selected_index = anthropic_models.index(llm_model_name)
                    st_llm_model_name = st.selectbox(
                        tr("Model Name"),
                        options=anthropic_models,
                        index=selected_index,
                        key="anthropic_model_name_select",
                    )
                    anthropic_custom_model = st.text_input(
                        tr("Anthropic Custom Model ID"),
                        value="",
                        key="anthropic_custom_model_input",
                        placeholder="claude-sonnet-4-5-20250929",
                    )
                    if anthropic_custom_model.strip():
                        st_llm_model_name = anthropic_custom_model.strip()
                elif llm_provider == "bedrock":
                    from app.services.llm import is_bedrock_mantle_responses_model

                    bedrock_models = list(getattr(llm, "BEDROCK_MODEL_OPTIONS", []) or [])
                    if not bedrock_models:
                        st.error(tr("Bedrock Model List Unavailable"))
                        bedrock_models = [llm_model_name or getattr(llm, "DEFAULT_BEDROCK_SELECT_MODEL", "")]
                    if llm_model_name and llm_model_name not in bedrock_models:
                        bedrock_models.insert(0, llm_model_name)
                    selected_index = 0
                    if llm_model_name in bedrock_models:
                        selected_index = bedrock_models.index(llm_model_name)
                    st_llm_model_name = st.selectbox(
                        tr("Model Name"),
                        options=bedrock_models,
                        index=selected_index,
                        key="bedrock_model_name_select",
                    )
                    st.caption(tr("Bedrock Model Select Hint"))
                    bedrock_custom_model = st.text_input(
                        tr("Bedrock Custom Model ID"),
                        value="",
                        key="bedrock_custom_model_input",
                        placeholder="anthropic.claude-...",
                    )
                    if bedrock_custom_model.strip():
                        st_llm_model_name = bedrock_custom_model.strip()
                    if is_bedrock_mantle_responses_model(st_llm_model_name):
                        st.caption(tr("Bedrock Mantle OpenAI Hint"))
                else:
                    st_llm_model_name = st.text_input(
                        tr("Model Name"),
                        value=llm_model_name,
                        key=f"{llm_provider}_model_name_input",
                    )
                if st_llm_model_name:
                    config.app[f"{llm_provider}_model_name"] = st_llm_model_name
            else:
                st_llm_model_name = None

            if st_llm_api_key:
                config.app[f"{llm_provider}_api_key"] = st_llm_api_key
            if st_llm_base_url:
                config.app[f"{llm_provider}_base_url"] = st_llm_base_url
            if llm_provider == "ernie":
                st_llm_secret_key = st.text_input(
                    tr("Secret Key"), value=llm_secret_key, type="password"
                )
                config.app[f"{llm_provider}_secret_key"] = st_llm_secret_key

            if llm_provider == "cloudflare":
                st_llm_account_id = st.text_input(
                    tr("Account ID"), value=llm_account_id
                )
                if st_llm_account_id:
                    config.app[f"{llm_provider}_account_id"] = st_llm_account_id

        # 右侧面板 - API 密钥设置
        with right_config_panel:

            def get_keys_from_config(cfg_key):
                api_keys = config.app.get(cfg_key, [])
                if isinstance(api_keys, str):
                    api_keys = [api_keys]
                api_key = ", ".join(api_keys)
                return api_key

            def save_keys_to_config(cfg_key, value):
                value = value.replace(" ", "")
                if value:
                    config.app[cfg_key] = value.split(",")

            st.write(tr("Video Source Settings"))

            pexels_api_key = get_keys_from_config("pexels_api_keys")
            pexels_api_key = st.text_input(
                tr("Pexels API Key"), value=pexels_api_key, type="password"
            )
            save_keys_to_config("pexels_api_keys", pexels_api_key)

            pixabay_api_key = get_keys_from_config("pixabay_api_keys")
            pixabay_api_key = st.text_input(
                tr("Pixabay API Key"), value=pixabay_api_key, type="password"
            )
            save_keys_to_config("pixabay_api_keys", pixabay_api_key)

            coverr_api_key = get_keys_from_config("coverr_api_keys")
            coverr_api_key = st.text_input(
                tr("Coverr API Key"), value=coverr_api_key, type="password"
            )
            save_keys_to_config("coverr_api_keys", coverr_api_key)

with tab_create:
    cockpit._init_cockpit_session_state()

    params = VideoParams(video_subject="")
    params.match_materials_to_script = bool(
        st.session_state.get("match_materials_to_script", False)
    )
    script_mode = st.session_state.get("script_mode", "auto")
    cockpit.assign_model_fields(params, script_mode=script_mode)
    uploaded_files = []
    uploaded_audio_file = None

    active_slug = st.session_state.get("active_channel")
    active_channel_config = {}
    channel_runtime = st.session_state.get("channel_runtime") or {}
    if active_slug:
        try:
            active_channel_config = cockpit.load_channel_config(active_slug)
            if not channel_runtime:
                channel_runtime = cockpit.build_runtime_config(active_slug)
        except FileNotFoundError:
            active_channel_config = {}
            channel_runtime = {}

    video_source = str(
        st.session_state.get(
            "cockpit_video_source",
            config.ui.get("video_source", config.app.get("video_source", "collector")),
        )
        or "collector"
    )
    cockpit.render_ops_bar(tr, video_source)
    cockpit.render_pipeline_nav(tr)
    cockpit.render_production_summary(channel_runtime, tr)

    main_col, sidebar_col = st.columns([13, 7])
    main_panel = main_col
    side_panel = sidebar_col

    active_step = int(st.session_state.get("cockpit_active_step", 0) or 0)
    active_step = max(0, min(active_step, cockpit.PIPELINE_STEP_COUNT - 1))
    step_id = cockpit.STEP_IDS[active_step]

    inspector_callbacks = InspectorCallbacks(
        get_all_fonts=get_all_fonts,
        sync_chatterbox=_sync_chatterbox_config_from_session_state,
        detect_audio_mime=_detect_audio_mime,
        default_chatterbox_base_url=DEFAULT_CHATTERBOX_BASE_URL,
        default_chatterbox_model=DEFAULT_CHATTERBOX_MODEL,
        default_chatterbox_voices=DEFAULT_CHATTERBOX_VOICES,
        parse_chatterbox_voices=_parse_chatterbox_voices,
        llm_min_paragraphs=llm.MIN_SCRIPT_PARAGRAPH_NUMBER,
        llm_max_paragraphs=llm.MAX_SCRIPT_PARAGRAPH_NUMBER,
        llm_max_prompt=llm.MAX_SCRIPT_PROMPT_LENGTH,
        llm_max_system_prompt=llm.MAX_SCRIPT_SYSTEM_PROMPT_LENGTH,
    )

    def _render_idea_editor() -> None:
        cockpit.render_document_stage(tr("Cockpit Step Idea"))
        params.video_subject = st.text_input(
            tr("Video Subject"),
            key="video_subject",
            label_visibility="collapsed",
            placeholder=tr("Video Subject"),
        ).strip()

        cockpit.render_document_divider()
        cockpit.render_document_section_label(tr("Script Language"))
        video_languages = [(tr("Auto Detect"), "")]
        for code in support_locales:
            video_languages.append((code, code))

        selected_index = st.selectbox(
            tr("Script Language"),
            index=0,
            options=range(len(video_languages)),
            format_func=lambda x: video_languages[x][0],
            label_visibility="collapsed",
        )
        params.video_language = video_languages[selected_index][1]

    def _render_script_editor() -> None:
        cockpit.render_document_stage(tr("Cockpit Step Script"))
        params.video_script = st.text_area(
            tr("Video Script"),
            value=st.session_state["video_script"],
            height=420,
            label_visibility="collapsed",
        )
        cockpit.render_scene_breakdown(
            params.video_script,
            active_channel_config.get("scene_structure"),
            tr,
        )

        cockpit.render_document_divider()
        cockpit.render_document_section_label(tr("Title Overlay Enabled"))
        title_enabled = st.checkbox(
            tr("Title Overlay Enabled"),
            value=st.session_state.get(
                "title_enabled",
                active_channel_config.get("title_enabled", False),
            ),
            key="title_enabled",
            label_visibility="collapsed",
        )
        cockpit.assign_model_fields(params, title_enabled=title_enabled)
        if title_enabled:
            title_text = st.text_input(
                tr("Title Overlay Text"),
                value=st.session_state.get(
                    "title_text",
                    active_channel_config.get("title_text", params.video_subject),
                ),
                key="title_text",
            ).strip()
            title_duration = st.slider(
                tr("Title Overlay Duration"),
                min_value=1.0,
                max_value=8.0,
                value=float(
                    st.session_state.get(
                        "title_duration",
                        active_channel_config.get("title_duration", 3.0),
                    )
                ),
                step=0.5,
                key="title_duration",
            )
            cockpit.assign_model_fields(
                params,
                title_text=title_text,
                title_duration=title_duration,
            )
        else:
            cockpit.assign_model_fields(params, title_text="")

        cockpit.render_document_divider()
        cockpit.render_document_section_label(tr("Video Keywords"))
        st.markdown('<div class="cockpit-btn-important">', unsafe_allow_html=True)
        btn_cols = st.columns(2)
        with btn_cols[0]:
            if st.button(tr("Cockpit Generate Script"), key="auto_generate_script"):
                st.session_state["cockpit_trigger_generate_script"] = True
        with btn_cols[1]:
            if st.button(tr("Cockpit Generate Keywords"), key="auto_generate_terms"):
                st.session_state["cockpit_trigger_generate_keywords"] = True
        st.markdown("</div>", unsafe_allow_html=True)

        params.video_terms = st.text_area(
            tr("Video Keywords"),
            value=st.session_state["video_terms"],
            label_visibility="collapsed",
            height=120,
        )

    def _render_collector_editor() -> None:
        if cockpit.render_collector_panel(params, tr):
            cockpit.run_collector_fetch(params, tr)

    def _render_preview_editor() -> None:
        preview_btn, include_audio, skip_gate = cockpit.render_preview_editor(
            params,
            channel_runtime,
            tr,
            video_source=video_source,
        )
        st.session_state["_cockpit_preview_btn"] = preview_btn
        st.session_state["_cockpit_preview_audio"] = include_audio
        st.session_state["cockpit_skip_preview"] = skip_gate

    def _render_render_editor() -> None:
        st.session_state["_cockpit_full_btn"] = cockpit.render_render_editor(params, tr)

    def _render_result_editor() -> None:
        cockpit.render_result_editor(tr, open_folder_cb=open_task_folder)

    step_renderers = {
        0: _render_idea_editor,
        1: _render_script_editor,
        2: _render_collector_editor,
        3: _render_preview_editor,
        4: _render_render_editor,
        5: _render_result_editor,
    }

    with main_panel:
        st.markdown('<div class="cockpit-doc-workspace">', unsafe_allow_html=True)
        step_renderers[active_step]()
        st.markdown("</div>", unsafe_allow_html=True)

    preview_button = bool(st.session_state.pop("_cockpit_preview_btn", False))
    include_preview_audio = bool(st.session_state.pop("_cockpit_preview_audio", False))
    full_button = bool(st.session_state.pop("_cockpit_full_btn", False))
    skip_preview = bool(st.session_state.get("cockpit_skip_preview", False))

    with side_panel:
        st.markdown('<div class="cockpit-inspector-panel">', unsafe_allow_html=True)
        cockpit.render_stage_context(step_id, channel_runtime, params, tr)
        st.markdown(
            f'<div class="cockpit-section-title cockpit-inspector-settings-title">'
            f'{tr("Cockpit Stage Settings")}</div>',
            unsafe_allow_html=True,
        )
        uploaded_files, uploaded_audio_file = cockpit.render_stage_inspector(
            step_id,
            channel_runtime,
            params,
            tr,
            inspector_callbacks=inspector_callbacks,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    cockpit.sync_params_from_ui(params)
    video_source = params.video_source or video_source

    if st.session_state.pop("cockpit_trigger_generate_script", False):
        with st.spinner(tr("Generating Video Script and Keywords")):
            current_script_mode = st.session_state.get("script_mode", "auto")
            if current_script_mode == "polish":
                if not params.video_script.strip():
                    st.error(tr("Script Mode Polish Brief Required"))
                else:
                    script = llm.polish_script(
                        brief=params.video_script.strip(),
                        video_subject=params.video_subject,
                        duration_seconds=max(30, params.paragraph_number * 25),
                        language=params.video_language or "",
                    )
                    terms = llm.generate_terms(
                        params.video_subject,
                        script,
                        amount=8 if params.match_materials_to_script else 5,
                        match_script_order=params.match_materials_to_script,
                    )
                    if _is_terms_error(terms):
                        st.error(tr(terms))
                    else:
                        st.session_state["video_script"] = script
                        st.session_state["video_terms"] = _format_generated_terms(terms)
                        st.session_state["cockpit_active_step"] = 1
            elif current_script_mode == "verbatim" and params.video_script.strip():
                script = params.video_script.strip()
                terms = llm.generate_terms(
                    params.video_subject,
                    script,
                    amount=8 if params.match_materials_to_script else 5,
                    match_script_order=params.match_materials_to_script,
                )
                if _is_terms_error(terms):
                    st.error(tr(terms))
                else:
                    st.session_state["video_terms"] = _format_generated_terms(terms)
            else:
                script = llm.generate_script(
                    video_subject=params.video_subject,
                    language=params.video_language,
                    paragraph_number=params.paragraph_number,
                    video_script_prompt=params.video_script_prompt,
                    custom_system_prompt=params.custom_system_prompt,
                )
                terms = llm.generate_terms(
                    params.video_subject,
                    script,
                    amount=8 if params.match_materials_to_script else 5,
                    match_script_order=params.match_materials_to_script,
                )
                if "Error: " in script:
                    st.error(tr(script))
                elif _is_terms_error(terms):
                    st.error(tr(terms))
                else:
                    st.session_state["video_script"] = script
                    st.session_state["video_terms"] = _format_generated_terms(terms)
                    st.session_state["cockpit_active_step"] = 1

    if st.session_state.pop("cockpit_trigger_generate_keywords", False):
        if not params.video_script:
            st.error(tr("Please Enter the Video Subject"))
        else:
            with st.spinner(tr("Generating Video Keywords")):
                terms = llm.generate_terms(
                    params.video_subject,
                    params.video_script,
                    amount=8 if params.match_materials_to_script else 5,
                    match_script_order=params.match_materials_to_script,
                )
                if _is_terms_error(terms):
                    st.error(tr(terms))
                else:
                    st.session_state["video_terms"] = _format_generated_terms(terms)

    st.divider()
    render_blockers = cockpit.list_render_blockers(
        params.video_source,
        params.voice_name,
        tr,
    )
    if render_blockers:
        st.warning(
            tr("Cockpit Render Blocked") + "\n\n"
            + "\n".join(f"- {item}" for item in render_blockers)
        )
    active_lock = generation_lock_status()
    if active_lock:
        st.error(
            f"{tr('Cockpit Generation Locked')}: `{active_lock.get('task_id', 'unknown')}`"
        )
    cockpit.render_provider_center(
        params.video_source,
        params.voice_name,
        tr,
    )

    if preview_button:
        config.save_config()
        preview_task_id = str(uuid4())
        st.session_state["last_preview_task_id"] = preview_task_id
        cockpit.run_preview(params, include_preview_audio, tr, root_dir)
        scroll_to_bottom()

    if full_button:
        if not st.session_state.get("preview_ready") and not skip_preview:
            st.warning(tr("Cockpit Preview Required"))
            scroll_to_bottom()
            st.stop()

        config.save_config()
        task_id = str(uuid4())
        if not params.video_subject and not params.video_script:
            st.error(tr("Video Script and Subject Cannot Both Be Empty"))
            scroll_to_bottom()
            st.stop()

        if params.video_source not in ["pexels", "pixabay", "coverr", "collector", "local"]:
            st.error(tr("Please Select a Valid Video Source"))
            scroll_to_bottom()
            st.stop()

        if params.video_source == "collector":
            if not (config.app.get("collector_base_url") or "").strip():
                st.error(tr("Please configure the Collector base URL"))
                scroll_to_bottom()
                st.stop()
            if not (config.app.get("collector_remote_dir") or "").strip() or not (
                config.app.get("collector_local_dir") or ""
            ).strip():
                st.error(tr("Please configure Collector remote and local directories"))
                scroll_to_bottom()
                st.stop()

        if params.video_source == "pexels" and not config.app.get("pexels_api_keys", ""):
            st.error(tr("Please Enter the Pexels API Key"))
            scroll_to_bottom()
            st.stop()

        if params.video_source == "pixabay" and not config.app.get("pixabay_api_keys", ""):
            st.error(tr("Please Enter the Pixabay API Key"))
            scroll_to_bottom()
            st.stop()

        if params.video_source == "coverr" and not config.app.get("coverr_api_keys", ""):
            st.error(tr("Please Enter the Coverr API Key"))
            scroll_to_bottom()
            st.stop()

        if uploaded_audio_file:
            task_dir = utils.task_dir(task_id)
            _, audio_ext = os.path.splitext(os.path.basename(uploaded_audio_file.name))
            audio_ext = audio_ext.lower() or ".mp3"
            custom_audio_path = os.path.join(task_dir, f"custom-audio{audio_ext}")
            with open(custom_audio_path, "wb") as f:
                f.write(uploaded_audio_file.getbuffer())
            params.custom_audio_file = custom_audio_path

        if uploaded_files:
            local_videos_dir = utils.storage_dir("local_videos", create=True)
            params.video_materials = []
            persisted_local_materials = []
            for file in uploaded_files:
                file_path = os.path.join(local_videos_dir, f"{file.file_id}_{file.name}")
                with open(file_path, "wb") as f:
                    f.write(file.getbuffer())
                    m = MaterialInfo()
                    m.provider = "local"
                    m.url = file_path
                    params.video_materials.append(m)
                    persisted_local_materials.append(
                        {
                            "provider": m.provider,
                            "url": m.url,
                            "duration": m.duration,
                        }
                    )
            st.session_state["local_video_materials"] = persisted_local_materials
        elif params.video_source == "local" and st.session_state["local_video_materials"]:
            params.video_materials = []
            for material in st.session_state["local_video_materials"]:
                m = MaterialInfo()
                m.provider = material.get("provider", "local")
                m.url = material.get("url", "")
                m.duration = material.get("duration", 0)
                if m.url:
                    params.video_materials.append(m)

        log_container = st.empty()
        log_records = []

        def log_received(msg):
            if config.ui["hide_log"]:
                return
            with log_container:
                log_records.append(msg)
                st.code("\n".join(log_records))

        logger.add(log_received)

        with st.status(tr("Cockpit Status Rendering"), expanded=True) as status:
            status.write(tr("Cockpit Step Validate"))
            status.write(tr("Cockpit Step Running"))
            st.toast(tr("Generating Video"))
            logger.info(tr("Start Generating Video"))
            logger.info(utils.to_json(params))
            try:
                with single_flight_generation_lock(task_id):
                    result = tm.start(task_id=task_id, params=params)
            except GenerationAlreadyRunningError as exc:
                status.update(state="error")
                st.error(f"{tr('Cockpit Generation Locked')}: `{exc}`")
                scroll_to_bottom()
                st.stop()
            if not result or "videos" not in result:
                status.update(state="error")
                st.error(tr("Video Generation Failed"))
                logger.error(tr("Video Generation Failed"))
                scroll_to_bottom()
                st.stop()
            status.update(label=tr("Cockpit Render Done"), state="complete")

        video_files = result.get("videos", [])
        st.success(tr("Video Generation Completed"))
        cockpit.render_clip_diagnosis(result, tr)
        cockpit.render_bgm_audit_warning(task_id, params.bgm_type or "", tr)
        st.session_state["preview_ready"] = False
        st.session_state["last_render_task_id"] = task_id
        st.session_state["cockpit_active_step"] = 5
        try:
            if video_files:
                player_cols = st.columns(len(video_files) * 2 + 1)
                for i, url in enumerate(video_files):
                    player_cols[i * 2 + 1].video(url)
        except Exception:
            pass

        open_task_folder(task_id)
        logger.info(tr("Video Generation Completed"))
        scroll_to_bottom()

config.save_config()
