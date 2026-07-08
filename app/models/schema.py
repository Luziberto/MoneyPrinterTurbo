import re
import warnings
from enum import Enum
from typing import Any, List, Literal, Optional, Union

import pydantic
from pydantic import BaseModel, Field

# 忽略 Pydantic 的特定警告
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Field name.*shadows an attribute in parent.*",
)


class VideoConcatMode(str, Enum):
    random = "random"
    sequential = "sequential"


class VideoTransitionMode(str, Enum):
    none = None
    shuffle = "Shuffle"
    fade_in = "FadeIn"
    fade_out = "FadeOut"
    slide_in = "SlideIn"
    slide_out = "SlideOut"


class VideoAspect(str, Enum):
    landscape = "16:9"
    portrait = "9:16"
    square = "1:1"

    def to_resolution(self):
        if self == VideoAspect.landscape:
            return 1920, 1080
        elif self == VideoAspect.portrait:
            return 1080, 1920
        elif self == VideoAspect.square:
            return 1080, 1080
        raise ValueError(f"unsupported video aspect: {self}")


class _Config:
    arbitrary_types_allowed = True


@pydantic.dataclasses.dataclass(config=_Config)
class MaterialInfo:
    provider: str = "pexels"
    url: str = ""
    duration: int = 0
    width: int = 0
    height: int = 0
    search_term: str = ""
    metadata_text: str = ""
    score: int = 0


class CollectorKeyword(BaseModel):
    term: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class CollectorChannelConfig(BaseModel):
    target_clips: int = Field(default=25, ge=1)
    min_acceptable_clips: int = Field(default=20, ge=1)


class NormalizedCollectorKeywords(BaseModel):
    keywords: List[CollectorKeyword] = Field(default_factory=list)
    has_explicit_weights: bool = False


DEFAULT_COLLECTOR_TARGET_CLIPS = 25
DEFAULT_COLLECTOR_MIN_ACCEPTABLE_CLIPS = 20


def resolve_collector_clip_limits(
    target_clips: int | None = None,
    min_acceptable_clips: int | None = None,
) -> CollectorChannelConfig:
    target = max(1, int(target_clips or DEFAULT_COLLECTOR_TARGET_CLIPS))
    default_min = min(DEFAULT_COLLECTOR_MIN_ACCEPTABLE_CLIPS, target)
    try:
        minimum = int(min_acceptable_clips if min_acceptable_clips is not None else default_min)
    except (TypeError, ValueError):
        minimum = default_min
    minimum = max(1, min(minimum, target))
    return CollectorChannelConfig(target_clips=target, min_acceptable_clips=minimum)


def normalize_collector_keywords(
    raw_terms: str | list | None,
) -> NormalizedCollectorKeywords:
    if raw_terms is None:
        return NormalizedCollectorKeywords()

    items: list[Any]
    if isinstance(raw_terms, str):
        items = [part.strip() for part in re.split(r"[,，]", raw_terms) if part.strip()]
        has_explicit_weights = False
    elif isinstance(raw_terms, list):
        items = raw_terms
        has_explicit_weights = any(
            isinstance(item, CollectorKeyword)
            or (isinstance(item, dict) and "weight" in item)
            for item in items
        )
    else:
        raise ValueError("video_terms must be a string or a list of keywords.")

    keywords: list[CollectorKeyword] = []
    for item in items:
        if isinstance(item, CollectorKeyword):
            term = item.term.strip()
            if term:
                keywords.append(item.model_copy(update={"term": term}))
            continue
        if isinstance(item, dict):
            term = str(item.get("term", "")).strip()
            if not term:
                continue
            try:
                weight = float(item.get("weight", 1.0))
            except (TypeError, ValueError):
                weight = 1.0
            keywords.append(
                CollectorKeyword(term=term, weight=max(0.0, min(1.0, weight)))
            )
            continue
        term = str(item).strip()
        if term:
            keywords.append(CollectorKeyword(term=term, weight=1.0))

    return NormalizedCollectorKeywords(
        keywords=keywords,
        has_explicit_weights=has_explicit_weights,
    )


def collector_keywords_to_strings(keywords: str | list | None) -> list[str]:
    return [
        keyword.term
        for keyword in normalize_collector_keywords(keywords).keywords
        if keyword.term
    ]


def format_collector_keywords_for_ui(keywords: str | list | None) -> str:
    normalized = normalize_collector_keywords(keywords)
    if not normalized.keywords:
        return ""
    if normalized.has_explicit_weights:
        return ", ".join(
            f"{keyword.term} ({keyword.weight:g})"
            for keyword in normalized.keywords
        )
    return ", ".join(keyword.term for keyword in normalized.keywords)


class CollectorJobError(BaseModel):
    code: str = ""
    message: str = ""


class CollectorSelectedClip(BaseModel):
    path: str
    score: float = 0.0
    retrieval_score: float = 0.0
    visual_score: float = 0.0
    duration: float = 0.0
    matched_keyword: str = ""
    source: str = ""
    width: int = 0
    height: int = 0
    recommended_clip_duration: Optional[float] = None
    keyword_scores: Optional[dict[str, float]] = None
    asset_id: str = ""
    clip_id: str = ""


class CollectorJobRequest(BaseModel):
    client_task_id: str
    keywords: List[CollectorKeyword]
    target_clips: int = Field(default=25, ge=1)
    min_acceptable_clips: int = Field(default=20, ge=1)


class CollectorJobResult(BaseModel):
    job_id: str = ""
    status: str = ""
    target_clips: int = 0
    selected_clips_count: int = 0
    min_acceptable_clips: int = 0
    local_reused: int = 0
    new_downloads: int = 0
    selected_clips: List[CollectorSelectedClip] = Field(default_factory=list)
    clips_file: str = ""
    error: Optional[CollectorJobError] = None


class VideoParams(BaseModel):
    """
    {
      "video_subject": "",
      "video_aspect": "横屏 16:9（西瓜视频）",
      "voice_name": "女生-晓晓",
      "bgm_name": "random",
      "font_name": "STHeitiMedium 黑体-中",
      "text_color": "#FFFFFF",
      "font_size": 60,
      "stroke_color": "#000000",
      "stroke_width": 1.5
    }
    """

    video_subject: str
    video_script: str = ""  # Script used to generate the video
    script_mode: Optional[Literal["auto", "verbatim", "polish"]] = None
    script_brief: Optional[str] = None
    video_terms: Optional[str | list] = None  # Keywords used to generate the video
    video_aspect: Optional[VideoAspect] = VideoAspect.portrait.value
    video_concat_mode: Optional[VideoConcatMode] = VideoConcatMode.random.value
    video_transition_mode: Optional[VideoTransitionMode] = None
    video_clip_duration: Optional[int] = 5
    match_materials_to_script: bool = False
    video_count: Optional[int] = 1

    video_source: Optional[str] = "pexels"
    video_materials: Optional[List[MaterialInfo]] = (
        None  # Materials used to generate the video
    )
    video_clips: Optional[List[CollectorSelectedClip]] = None
    
    custom_audio_file: Optional[str] = None  # Custom audio file path, will ignore TTS and can still use Whisper subtitles
    video_language: Optional[str] = ""  # auto detect

    voice_name: Optional[str] = ""
    voice_volume: Optional[float] = 1.0
    voice_rate: Optional[float] = 1.0
    bgm_type: Optional[str] = "random"
    bgm_file: Optional[str] = ""
    bgm_profile: Optional[str] = ""
    bgm_volume: Optional[float] = 0.2

    subtitle_enabled: Optional[bool] = True
    subtitle_position: Optional[str] = "bottom"  # top, bottom, center, custom
    custom_position: float = 70.0
    font_name: Optional[str] = "STHeitiMedium.ttc"
    text_fore_color: Optional[str] = "#FFFFFF"
    text_background_color: Union[bool, str] = True
    rounded_subtitle_background: bool = False

    font_size: int = 60
    stroke_color: Optional[str] = "#000000"
    stroke_width: float = 1.5
    n_threads: Optional[int] = 2
    paragraph_number: int = Field(default=1, ge=1, le=10)
    video_script_prompt: str = Field(default="", max_length=2000)
    custom_system_prompt: str = Field(default="", max_length=8000)

    title_enabled: bool = False
    title_text: str = ""
    title_duration: float = 3.0
    title_background_overlay: bool = True
    title_overlay_color: Optional[str] = "rgba(0,0,0,0.5)"
    scene_structure: Optional[List[str]] = None

    collector_target_clips: Optional[int] = None
    collector_min_acceptable_clips: Optional[int] = None
    channel_slug: Optional[str] = None
    publish_platforms: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Cockpit workspace — server-side draft state for the Vue cockpit, replacing
# Streamlit's st.session_state. One Workspace per channel_slug, persisted by
# app/services/workspace_store.py. See pipeline/README.md-adjacent
# webui-vue migration plan for the full field-by-field mapping from
# webui/cockpit.py's session_state keys.
# ---------------------------------------------------------------------------


class WorkspaceScript(BaseModel):
    video_subject: str = ""
    video_script: str = ""
    script_mode: Literal["auto", "verbatim", "polish"] = "auto"
    video_language: str = ""
    paragraph_number: int = 1
    video_script_prompt: str = ""
    use_custom_system_prompt: bool = False
    custom_system_prompt: str = ""
    match_materials_to_script: bool = False


class WorkspaceKeywords(BaseModel):
    terms: List[CollectorKeyword] = Field(default_factory=list)
    has_explicit_weights: bool = False


class WorkspaceMedia(BaseModel):
    video_source: str = "pexels"
    video_aspect: str = VideoAspect.portrait.value
    video_concat_mode: str = VideoConcatMode.random.value
    video_transition_mode: Optional[str] = None
    video_clip_duration: int = 3
    video_count: int = 1
    collector_target_clips: Optional[int] = None
    collector_min_acceptable_clips: Optional[int] = None
    last_collector_job: Optional[dict] = None
    video_materials: Optional[List[MaterialInfo]] = None
    video_clips: Optional[List[CollectorSelectedClip]] = None


class WorkspaceVoice(BaseModel):
    voice_name: str = ""
    voice_volume: float = 1.0
    voice_rate: float = 1.0
    tts_server: str = "azure-tts-v1"
    custom_audio_file: Optional[str] = None


class WorkspaceBgm(BaseModel):
    bgm_type: str = "random"
    bgm_profile: str = ""
    bgm_file: str = ""
    bgm_volume: float = 0.2


class WorkspaceSubtitle(BaseModel):
    subtitle_enabled: bool = True
    font_name: str = "Roboto-Bold.ttf"
    font_size: int = 55
    subtitle_position: str = "bottom"
    custom_position: float = 70.0
    text_fore_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: float = 2.5
    subtitle_background_enabled: bool = True
    subtitle_background_color: str = "#000000"
    rounded_subtitle_background: bool = False


class WorkspaceTitleOverlay(BaseModel):
    title_enabled: bool = False
    title_text: str = ""
    title_duration: float = 3.0


class WorkspacePreviewState(BaseModel):
    ready: bool = False
    last_preview_at: Optional[str] = None
    last_preview_task_id: Optional[str] = None


class WorkspaceRenderState(BaseModel):
    last_render_task_id: Optional[str] = None
    skip_preview: bool = False


class WorkspacePublishState(BaseModel):
    mode: Literal["manual", "auto", "skip"] = "manual"
    platforms: List[str] = Field(default_factory=list)
    auto_upload: bool = False
    youtube_privacy_status: str = "unlisted"
    last_results: Optional[List[dict]] = None
    done: bool = False


class Workspace(BaseModel):
    channel_slug: Optional[str] = None
    active_step: int = Field(default=0, ge=0, le=5)
    updated_at: Optional[str] = None

    script: WorkspaceScript = Field(default_factory=WorkspaceScript)
    keywords: WorkspaceKeywords = Field(default_factory=WorkspaceKeywords)
    media: WorkspaceMedia = Field(default_factory=WorkspaceMedia)
    voice: WorkspaceVoice = Field(default_factory=WorkspaceVoice)
    bgm: WorkspaceBgm = Field(default_factory=WorkspaceBgm)
    subtitle: WorkspaceSubtitle = Field(default_factory=WorkspaceSubtitle)
    title_overlay: WorkspaceTitleOverlay = Field(default_factory=WorkspaceTitleOverlay)

    overrides: List[str] = Field(default_factory=list)

    preview: WorkspacePreviewState = Field(default_factory=WorkspacePreviewState)
    render: WorkspaceRenderState = Field(default_factory=WorkspaceRenderState)
    publish: WorkspacePublishState = Field(default_factory=WorkspacePublishState)


class WorkspacePatch(BaseModel):
    """Partial update body for PATCH /cockpit/workspace.

    Each field is a partial dict merged into the matching Workspace group
    (deep merge, not replace) by app/services/workspace_store.py. Kept loosely
    typed (dict, not the group model) so the client can send only the keys
    that changed without re-sending an entire group.
    """

    active_step: Optional[int] = Field(default=None, ge=0, le=5)
    script: Optional[dict] = None
    keywords: Optional[dict] = None
    media: Optional[dict] = None
    voice: Optional[dict] = None
    bgm: Optional[dict] = None
    subtitle: Optional[dict] = None
    title_overlay: Optional[dict] = None
    preview: Optional[dict] = None
    render: Optional[dict] = None
    publish: Optional[dict] = None


class ChannelSummary(BaseModel):
    slug: str
    name: str
    niche: str = ""
    mode: str = "faceless"
    video_source: str = "pexels"


class ChannelConfigResponse(BaseModel):
    slug: str
    config: dict
    runtime: dict


class SubtitleRequest(BaseModel):
    video_script: str
    video_language: Optional[str] = ""
    voice_name: Optional[str] = "zh-CN-XiaoxiaoNeural-Female"
    voice_volume: Optional[float] = 1.0
    voice_rate: Optional[float] = 1.2
    bgm_type: Optional[str] = "random"
    bgm_file: Optional[str] = ""
    bgm_profile: Optional[str] = ""
    bgm_volume: Optional[float] = 0.2
    subtitle_position: Optional[str] = "bottom"
    font_name: Optional[str] = "STHeitiMedium.ttc"
    text_fore_color: Optional[str] = "#FFFFFF"
    text_background_color: Union[bool, str] = True
    rounded_subtitle_background: bool = False
    font_size: int = 60
    stroke_color: Optional[str] = "#000000"
    stroke_width: float = 1.5
    video_source: Optional[str] = "local"
    subtitle_enabled: Optional[str] = "true"


class AudioRequest(BaseModel):
    video_script: str
    video_language: Optional[str] = ""
    voice_name: Optional[str] = "zh-CN-XiaoxiaoNeural-Female"
    voice_volume: Optional[float] = 1.0
    voice_rate: Optional[float] = 1.2
    bgm_type: Optional[str] = "random"
    bgm_file: Optional[str] = ""
    bgm_profile: Optional[str] = ""
    bgm_volume: Optional[float] = 0.2
    video_source: Optional[str] = "local"


class VideoScriptParams:
    """
    {
      "video_subject": "春天的花海",
      "video_language": "",
      "paragraph_number": 1,
      "video_script_prompt": "",
      "custom_system_prompt": ""
    }
    """

    video_subject: Optional[str] = "春天的花海"
    video_language: Optional[str] = ""
    paragraph_number: int = Field(default=1, ge=1, le=10)
    video_script_prompt: str = Field(default="", max_length=2000)
    custom_system_prompt: str = Field(default="", max_length=8000)


class VideoTermsParams:
    """
    {
      "video_subject": "",
      "video_script": "",
      "amount": 5,
      "match_materials_to_script": false
    }
    """

    video_subject: Optional[str] = "春天的花海"
    video_script: Optional[str] = (
        "春天的花海，如诗如画般展现在眼前。万物复苏的季节里，大地披上了一袭绚丽多彩的盛装。金黄的迎春、粉嫩的樱花、洁白的梨花、艳丽的郁金香……"
    )
    amount: Optional[int] = 5
    match_materials_to_script: bool = False


class VideoSocialMetadataParams:
    """
    {
      "video_subject": "A day in Shanghai",
      "video_script": "",
      "language": "auto",
      "platform": "tiktok"
    }
    """

    video_subject: Optional[str] = Field(default="A day in Shanghai", max_length=500)
    video_script: Optional[str] = Field(default="", max_length=8000)
    language: Optional[str] = Field(default="auto", max_length=64)
    platform: Optional[str] = Field(default="tiktok", max_length=64)


class BaseResponse(BaseModel):
    status: int = 200
    message: Optional[str] = "success"
    data: Any = None


class TaskVideoRequest(VideoParams, BaseModel):
    pass


class TaskQueryRequest(BaseModel):
    pass


class VideoScriptRequest(VideoScriptParams, BaseModel):
    pass


class VideoTermsRequest(VideoTermsParams, BaseModel):
    pass


class VideoSocialMetadataRequest(VideoSocialMetadataParams, BaseModel):
    pass


######################################################################################################
######################################################################################################
######################################################################################################
######################################################################################################
class TaskResponse(BaseResponse):
    class TaskResponseData(BaseModel):
        task_id: str

    data: TaskResponseData

    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {"task_id": "6c85c8cc-a77a-42b9-bc30-947815aa0558"},
            },
        }


class TaskQueryResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "state": 1,
                    "progress": 100,
                    "videos": [
                        "http://127.0.0.1:8080/tasks/6c85c8cc-a77a-42b9-bc30-947815aa0558/final-1.mp4"
                    ],
                    "combined_videos": [
                        "http://127.0.0.1:8080/tasks/6c85c8cc-a77a-42b9-bc30-947815aa0558/combined-1.mp4"
                    ],
                },
            },
        }


class TaskDeletionResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "state": 1,
                    "progress": 100,
                    "videos": [
                        "http://127.0.0.1:8080/tasks/6c85c8cc-a77a-42b9-bc30-947815aa0558/final-1.mp4"
                    ],
                    "combined_videos": [
                        "http://127.0.0.1:8080/tasks/6c85c8cc-a77a-42b9-bc30-947815aa0558/combined-1.mp4"
                    ],
                },
            },
        }


class VideoScriptResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "video_script": "春天的花海，是大自然的一幅美丽画卷。在这个季节里，大地复苏，万物生长，花朵争相绽放，形成了一片五彩斑斓的花海..."
                },
            },
        }


class VideoTermsResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {"video_terms": ["sky", "tree"]},
            },
        }


class VideoSocialMetadataResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "title": "A Day in Shanghai You Should Not Miss",
                    "caption": "Save this quick Shanghai inspiration and follow for more short travel ideas.",
                    "hashtags": ["#shorts", "#travel", "#shanghai", "#viral", "#fyp"],
                },
            },
        }


class BgmRetrieveResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "files": [
                        {
                            "name": "output013.mp3",
                            "size": 1891269,
                            "file": "/MoneyPrinterTurbo/resource/songs/output013.mp3",
                        }
                    ]
                },
            },
        }


class BgmUploadResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {"file": "/MoneyPrinterTurbo/resource/songs/example.mp3"},
            },
        }

class VideoMaterialRetrieveResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "files": [
                        {
                            "name": "example.mp4",
                            "size": 12345678,
                            "file": "/MoneyPrinterTurbo/resource/videos/example.mp4",
                        }
                    ]
                },
            },
        }

class VideoMaterialUploadResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "file": "/MoneyPrinterTurbo/resource/videos/example.mp4",
                },
            },
        }
