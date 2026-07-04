import os
import random
import shutil
import threading
from typing import List, Union
from urllib.parse import urlencode

import requests
from loguru import logger
from moviepy.video.io.VideoFileClip import VideoFileClip

from app.config import config
from app.models.schema import (
    CollectorJobRequest,
    CollectorSelectedClip,
    MaterialInfo,
    VideoAspect,
    VideoConcatMode,
)
from app.services import collector_client
from app.utils import file_security, utils

# Thread-safe counter for API key rotation
_api_key_counter = 0
_api_key_lock = threading.Lock()

MATERIAL_SCORE_TOP_N = 30
SCORE_PORTRAIT_OR_MATCHING_ORIENTATION = 5
SCORE_TARGET_RESOLUTION = 3
SCORE_MIN_DURATION = 2
SCORE_KEYWORD_MATCH = 2
SCORE_MIN_DURATION_SECONDS = 6
_KEYWORD_STOPWORDS = frozenset({"in", "at", "on", "of", "to", "a", "an", "the", "and", "or"})


def _get_tls_verify() -> bool:
    # 默认开启 TLS 证书校验，防止素材搜索和下载过程被中间人篡改。
    # 仅在企业代理、自签证书等明确需要的场景下，允许用户通过
    # `config.toml` 显式设置 `tls_verify = false` 临时关闭。
    tls_verify = config.app.get("tls_verify", True)
    if isinstance(tls_verify, str):
        tls_verify = tls_verify.strip().lower() not in ("0", "false", "no", "off")

    if not tls_verify:
        logger.warning(
            "TLS certificate verification is disabled by config.app.tls_verify=false. "
            "Only use this in trusted proxy environments."
        )

    return bool(tls_verify)


def get_api_key(cfg_key: str):
    api_keys = config.app.get(cfg_key)
    if not api_keys:
        raise ValueError(
            f"\n\n##### {cfg_key} is not set #####\n\nPlease set it in the config.toml file: {config.config_file}\n\n"
            f"{utils.to_json(config.app)}"
        )

    # if only one key is provided, return it
    if isinstance(api_keys, str):
        return api_keys

    global _api_key_counter
    with _api_key_lock:
        _api_key_counter += 1
        return api_keys[_api_key_counter % len(api_keys)]


def _aspect_ratio_to_dimensions(aspect_ratio: str) -> tuple[int, int]:
    ratio = (aspect_ratio or "").strip().replace(" ", "")
    mapping = {
        "16:9": (1920, 1080),
        "9:16": (1080, 1920),
        "1:1": (1080, 1080),
        "4:3": (1440, 1080),
        "3:4": (1080, 1440),
    }
    return mapping.get(ratio, (0, 0))


def _keyword_tokens(search_term: str) -> List[str]:
    tokens = []
    for token in (search_term or "").lower().replace(",", " ").split():
        cleaned = token.strip(".,;:!?\"'()[]{}")
        if len(cleaned) > 2 and cleaned not in _KEYWORD_STOPWORDS:
            tokens.append(cleaned)
    return tokens


def _matches_keyword(item: MaterialInfo) -> bool:
    tokens = _keyword_tokens(item.search_term)
    if not tokens:
        return False
    haystack = f"{item.metadata_text} {item.url}".lower()
    return any(token in haystack for token in tokens)


def _orientation_matches(item: MaterialInfo, video_aspect: VideoAspect) -> bool:
    if item.width <= 0 or item.height <= 0:
        return False
    if video_aspect == VideoAspect.portrait:
        return item.height > item.width
    if video_aspect == VideoAspect.landscape:
        return item.width > item.height
    if video_aspect == VideoAspect.square:
        return item.width == item.height
    return False


def _score_material(
    item: MaterialInfo,
    video_aspect: VideoAspect,
    target_w: int,
    target_h: int,
) -> int:
    score = 0
    if _orientation_matches(item, video_aspect):
        score += SCORE_PORTRAIT_OR_MATCHING_ORIENTATION
    if item.width >= target_w and item.height >= target_h:
        score += SCORE_TARGET_RESOLUTION
    if item.duration >= SCORE_MIN_DURATION_SECONDS:
        score += SCORE_MIN_DURATION
    if _matches_keyword(item):
        score += SCORE_KEYWORD_MATCH
    return score


def _rank_materials(
    items: List[MaterialInfo],
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    if not items:
        return []

    aspect = VideoAspect(video_aspect)
    target_w, target_h = aspect.to_resolution()

    for item in items:
        item.score = _score_material(item, aspect, target_w, target_h)

    ranked = sorted(items, key=lambda x: x.score, reverse=True)
    top_items = ranked[:MATERIAL_SCORE_TOP_N]

    scores = [item.score for item in top_items]
    logger.info(
        f"material ranking: {len(items)} candidates -> top {len(top_items)}, "
        f"score range {min(scores)}-{max(scores)}"
    )
    return top_items


def search_videos_pexels(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)
    video_orientation = aspect.name
    video_width, video_height = aspect.to_resolution()
    api_key = get_api_key("pexels_api_keys")
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    }
    # Build URL
    params = {"query": search_term, "per_page": 20, "orientation": video_orientation}
    query_url = f"https://api.pexels.com/videos/search?{urlencode(params)}"
    logger.info(f"searching videos: {query_url}, with proxies: {config.proxy}")

    try:
        r = requests.get(
            query_url,
            headers=headers,
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=(30, 60),
        )
        response = r.json()
        video_items = []
        if "videos" not in response:
            logger.error(f"search videos failed: {response}")
            return video_items
        videos = response["videos"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["video_files"]
            # loop through each url to determine the best quality
            for video in video_files:
                w = int(video["width"])
                h = int(video["height"])
                if w == video_width and h == video_height:
                    item = MaterialInfo()
                    item.provider = "pexels"
                    item.url = video["link"]
                    item.duration = duration
                    item.width = w
                    item.height = h
                    item.search_term = search_term
                    item.metadata_text = v.get("url", "")
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        logger.error(f"search videos failed: {str(e)}")

    return []


def search_videos_pixabay(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)

    video_width, video_height = aspect.to_resolution()

    api_key = get_api_key("pixabay_api_keys")
    # Build URL
    params = {
        "q": search_term,
        "video_type": "all",  # Accepted values: "all", "film", "animation"
        "per_page": 50,
        "key": api_key,
    }
    query_url = f"https://pixabay.com/api/videos/?{urlencode(params)}"
    logger.info(f"searching videos: {query_url}, with proxies: {config.proxy}")

    try:
        r = requests.get(
            query_url, proxies=config.proxy, verify=_get_tls_verify(), timeout=(30, 60)
        )
        response = r.json()
        video_items = []
        if "hits" not in response:
            logger.error(f"search videos failed: {response}")
            return video_items
        videos = response["hits"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["videos"]
            # loop through each url to determine the best quality
            for video_type in video_files:
                video = video_files[video_type]
                w = int(video["width"])
                h = int(video.get("height") or 0)
                if w >= video_width:
                    item = MaterialInfo()
                    item.provider = "pixabay"
                    item.url = video["url"]
                    item.duration = duration
                    item.width = w
                    item.height = h
                    item.search_term = search_term
                    item.metadata_text = v.get("tags", "")
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        logger.error(f"search videos failed: {str(e)}")

    return []


def search_videos_coverr(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    """
    Coverr (https://coverr.co) - free HD/4K stock videos,
    subject to Coverr license terms (https://coverr.co/license).

    Coverr API notes (based on official docs at api.coverr.co/docs/):
      - 鉴权: Authorization: Bearer <api_key>
      - 搜索端点: GET /videos?query=...,响应结构 {"hits": [...], ...}
      - 加 ?urls=true 在搜索响应里直接返回 mp4 直链
      - URL 是 signed JWT(绑定 API key,无过期时间)
      - Coverr 库以 16:9 横屏为主,9:16 portrait 占比极低(约 1%)
        因此本函数不做 aspect_ratio 过滤,由下游 video.py 的
        resize + letterbox 逻辑统一处理
      - duration 字段同时存在 number 和 string 两种形态,本函数都接受

    本函数使用 urls.mp4_download 字段作为下载地址 —— 按 Coverr 官方文档
    (https://api.coverr.co/docs/videos/#download-a-video) 的说法,
    GET 这个 URL 本身就被 Coverr 当作一次合法的 download 事件计入统计,
    无需再调用 PATCH /videos/:id/stats/downloads。
    """
    api_key = get_api_key("coverr_api_keys")
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {
        "query": search_term,
        "page_size": 20,
        "urls": "true",
        "sort": "popular",
    }
    query_url = f"https://api.coverr.co/videos?{urlencode(params)}"
    logger.info(f"searching videos: {query_url}, with proxies: {config.proxy}")

    try:
        r = requests.get(
            query_url,
            headers=headers,
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=(30, 60),
        )
        response = r.json()
        video_items: List[MaterialInfo] = []

        if not isinstance(response, dict) or "hits" not in response:
            logger.error(f"search videos failed: {response}")
            return video_items

        for v in response["hits"]:
            # duration 在不同响应里可能是 number(11.625) 或 string("10.500000")
            try:
                duration = int(float(v.get("duration") or 0))
            except (TypeError, ValueError):
                continue
            if duration < minimum_duration:
                continue

            video_id = v.get("id")
            mp4_download_url = (v.get("urls") or {}).get("mp4_download")
            if not video_id or not mp4_download_url:
                continue

            item = MaterialInfo()
            item.provider = "coverr"
            item.url = mp4_download_url
            item.duration = duration
            item.search_term = search_term
            aspect_ratio = v.get("aspect_ratio", "")
            item.width, item.height = _aspect_ratio_to_dimensions(aspect_ratio)
            metadata_parts = [
                v.get("title", ""),
                v.get("description", ""),
                " ".join(v.get("tags") or []),
            ]
            item.metadata_text = " ".join(
                part for part in metadata_parts if part
            )
            video_items.append(item)
        return video_items
    except Exception as e:
        logger.error(f"search videos failed: {str(e)}")

    return []


STOCK_VIDEO_PROVIDERS = (
    ("pexels", "search_videos_pexels", "pexels_api_keys"),
    ("pixabay", "search_videos_pixabay", "pixabay_api_keys"),
    ("coverr", "search_videos_coverr", "coverr_api_keys"),
)


def _normalize_video_url(video_url: str) -> str:
    return (video_url or "").split("?")[0]


def _has_api_key(cfg_key: str) -> bool:
    api_keys = config.app.get(cfg_key)
    if isinstance(api_keys, str):
        return bool(api_keys.strip())
    if isinstance(api_keys, list):
        return any(str(key).strip() for key in api_keys)
    return False


def _safe_search_provider(
    provider_name: str,
    search_fn,
    cfg_key: str,
    *,
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect,
) -> List[MaterialInfo]:
    if not _has_api_key(cfg_key):
        logger.warning(f"stock search skipped [{provider_name}]: {cfg_key} is not set")
        return []
    try:
        return search_fn(
            search_term=search_term,
            minimum_duration=minimum_duration,
            video_aspect=video_aspect,
        )
    except ValueError as exc:
        logger.warning(f"stock search skipped [{provider_name}]: {exc}")
        return []
    except Exception as exc:
        logger.error(f"stock search failed [{provider_name}]: {exc}")
        return []


def search_stock_videos(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    """Search Pexels, Pixabay, and Coverr; merge and dedupe by normalized URL."""
    merged: List[MaterialInfo] = []
    seen_urls: set[str] = set()

    for provider_name, search_fn_name, cfg_key in STOCK_VIDEO_PROVIDERS:
        search_fn = globals()[search_fn_name]
        items = _safe_search_provider(
            provider_name,
            search_fn,
            cfg_key,
            search_term=search_term,
            minimum_duration=minimum_duration,
            video_aspect=video_aspect,
        )
        logger.info(
            f"stock search [{provider_name}] found {len(items)} videos for '{search_term}'"
        )
        for item in items:
            normalized_url = _normalize_video_url(item.url)
            if not normalized_url or normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            item.provider = provider_name
            merged.append(item)

    return merged


def map_collector_path(remote_path: str) -> str:
    remote_dir = (config.app.get("collector_remote_dir") or "").rstrip("/")
    local_dir = (config.app.get("collector_local_dir") or "").rstrip("/")
    if not remote_dir or not local_dir:
        raise ValueError("collector_remote_dir and collector_local_dir must be configured")

    normalized_remote = os.path.normpath(remote_path or "")
    if not normalized_remote:
        raise ValueError("empty collector path is not allowed")

    relative = os.path.relpath(normalized_remote, remote_dir)
    if relative.startswith(".."):
        raise ValueError("path is outside collector remote dir")

    return file_security.resolve_path_within_directory(local_dir, relative)


def search_videos_collector(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    del video_aspect  # scoring handles aspect downstream
    hits = collector_client.search_collector_clips(search_term)
    video_items: List[MaterialInfo] = []

    for hit in hits:
        try:
            duration = int(float(hit.get("duration") or 0))
        except (TypeError, ValueError):
            continue
        if duration < minimum_duration:
            continue

        local_path = hit.get("local_path")
        if not local_path:
            continue

        item = MaterialInfo()
        item.provider = "collector"
        item.url = local_path
        item.duration = duration
        item.width = int(hit.get("width") or 0)
        item.height = int(hit.get("height") or 0)
        item.search_term = search_term
        metadata_parts = [
            hit.get("title", ""),
            hit.get("source_site", ""),
            hit.get("clip_id", ""),
        ]
        item.metadata_text = " ".join(part for part in metadata_parts if part)
        video_items.append(item)

    return video_items


def stage_collector_clip(remote_path: str, save_dir: str = "") -> str:
    if not save_dir:
        save_dir = utils.storage_dir("cache_videos")

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    try:
        source_path = map_collector_path(remote_path)
    except ValueError as exc:
        logger.warning(f"skip collector clip [{remote_path}]: {exc}")
        return ""

    path_hash = utils.md5(source_path)
    video_id = f"vid-{path_hash}"
    video_path = f"{save_dir}/{video_id}.mp4"

    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        logger.info(f"collector clip already staged: {video_path}")
        return video_path

    clip = None
    try:
        clip = VideoFileClip(source_path)
        duration = clip.duration
        fps = clip.fps
        if duration <= 0 or fps <= 0:
            logger.warning(f"invalid collector clip: {source_path}")
            return ""
    except Exception as exc:
        logger.warning(f"invalid collector clip: {source_path} => {exc}")
        return ""
    finally:
        if clip is not None:
            try:
                clip.close()
            except Exception as close_error:
                logger.warning(
                    f"failed to close collector clip: {source_path}, error: {close_error}"
                )

    try:
        shutil.copy2(source_path, video_path)
    except Exception as exc:
        logger.error(f"failed to stage collector clip: {source_path} => {exc}")
        return ""

    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        logger.info(f"collector clip staged: {video_path}")
        return video_path
    return ""


def _normalize_collector_path(remote_path: str) -> str:
    return os.path.normpath(remote_path or "")


def _resolve_material_directory(task_id: str) -> str:
    material_directory = config.app.get("material_directory", "").strip()
    if material_directory == "task":
        material_directory = utils.task_dir(task_id)
    elif material_directory and not os.path.isdir(material_directory):
        material_directory = ""
    return material_directory


def _config_bool(key: str, default: bool = False) -> bool:
    value = config.app.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _collector_target_clips() -> int:
    try:
        return max(1, int(config.app.get("collector_target_clips", 25)))
    except (TypeError, ValueError):
        return 25


def _collector_min_acceptable_clips(target_clips: int) -> int:
    default_value = min(20, target_clips)
    try:
        value = int(config.app.get("collector_min_acceptable_clips", default_value))
    except (TypeError, ValueError):
        value = default_value
    return max(1, min(value, target_clips))


def _collector_enable_legacy_fallback() -> bool:
    return _config_bool("collector_enable_legacy_fallback", False)


def _build_collector_job_request(
    task_id: str, search_terms: List[str]
) -> CollectorJobRequest:
    keywords = [term.strip() for term in search_terms if str(term).strip()]
    target_clips = _collector_target_clips()
    return CollectorJobRequest(
        client_task_id=f"mpt_{task_id}",
        keywords=keywords,
        target_clips=target_clips,
        min_acceptable_clips=_collector_min_acceptable_clips(target_clips),
    )


def _stage_selected_collector_clip(
    selected_clip: CollectorSelectedClip,
    save_dir: str = "",
) -> CollectorSelectedClip | None:
    staged_path = stage_collector_clip(selected_clip.path, save_dir=save_dir)
    if not staged_path:
        return None

    staged_clip = selected_clip.model_copy(update={"path": staged_path})
    return staged_clip


def download_videos_from_collector(
    task_id: str,
    search_terms: List[str],
    video_aspect: VideoAspect = VideoAspect.portrait,
    video_contact_mode: VideoConcatMode = VideoConcatMode.random,
    audio_duration: float = 0.0,
    max_clip_duration: int = 5,
) -> List[CollectorSelectedClip]:
    del video_aspect, video_contact_mode, audio_duration, max_clip_duration

    job_request = _build_collector_job_request(task_id, search_terms)
    if not job_request.keywords:
        raise collector_client.CollectorJobFailedError(
            "NO_KEYWORDS",
            "No valid keywords were provided for collector search",
        )

    job = collector_client.create_stock_job(job_request)
    logger.info(
        f"collector stock job created: job_id={job.job_id}, status={job.status}, "
        f"target_clips={job_request.target_clips}"
    )
    final_job = collector_client.wait_for_stock_job(job.job_id)
    selected_clips = collector_client.load_selected_clips(final_job)

    material_directory = _resolve_material_directory(task_id)
    staged_clips: List[CollectorSelectedClip] = []
    seen_paths: set[str] = set()
    for selected_clip in selected_clips:
        normalized_path = _normalize_collector_path(selected_clip.path)
        if not normalized_path or normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)

        try:
            logger.info(f"staging collector clip: {selected_clip.path}")
            staged_clip = _stage_selected_collector_clip(
                selected_clip=selected_clip,
                save_dir=material_directory,
            )
            if staged_clip:
                staged_clips.append(staged_clip)
        except Exception as exc:
            logger.error(
                f"failed to stage collector clip: {utils.to_json(selected_clip.model_dump())} => {exc}"
            )

        if len(staged_clips) >= job_request.target_clips:
            break

    min_acceptable_clips = (
        final_job.min_acceptable_clips or job_request.min_acceptable_clips
    )
    if len(staged_clips) < min_acceptable_clips:
        raise collector_client.CollectorJobFailedError(
            "NOT_ENOUGH_CLIPS",
            (
                f"Collector returned only {len(staged_clips)} usable clips, "
                f"minimum required is {min_acceptable_clips}"
            ),
        )

    logger.success(f"staged {len(staged_clips)} collector clips")
    return staged_clips


def _get_remote_search_fn(source: str):
    if source == "pixabay":
        return search_videos_pixabay
    if source == "coverr":
        return search_videos_coverr
    if source == "stock":
        return search_stock_videos
    return search_videos_pexels


def _download_videos_from_remote(
    task_id: str,
    search_terms: List[str],
    source: str = "pexels",
    video_aspect: VideoAspect = VideoAspect.portrait,
    video_contact_mode: VideoConcatMode = VideoConcatMode.random,
    audio_duration: float = 0.0,
    max_clip_duration: int = 5,
) -> List[str]:
    valid_video_items = []
    valid_video_urls = []
    found_duration = 0.0
    search_videos = _get_remote_search_fn(source)

    for search_term in search_terms:
        video_items = search_videos(
            search_term=search_term,
            minimum_duration=max_clip_duration,
            video_aspect=video_aspect,
        )
        logger.info(f"found {len(video_items)} videos for '{search_term}'")

        for item in video_items:
            normalized_url = _normalize_video_url(item.url)
            if normalized_url and normalized_url not in valid_video_urls:
                if not item.search_term:
                    item.search_term = search_term
                valid_video_items.append(item)
                valid_video_urls.append(normalized_url)
                found_duration += item.duration

    logger.info(
        f"found total videos: {len(valid_video_items)}, required duration: {audio_duration} seconds, found duration: {found_duration} seconds"
    )
    video_paths = []
    material_directory = _resolve_material_directory(task_id)
    valid_video_items = _rank_materials(valid_video_items, video_aspect)

    concat_mode_value = getattr(video_contact_mode, "value", video_contact_mode)
    if concat_mode_value == VideoConcatMode.random.value:
        random.shuffle(valid_video_items)

    total_duration = 0.0
    for item in valid_video_items:
        try:
            logger.info(f"downloading video [{item.provider}]: {item.url}")
            saved_video_path = save_video(
                video_url=item.url, save_dir=material_directory
            )
            if saved_video_path:
                logger.info(f"video saved: {saved_video_path}")
                video_paths.append(saved_video_path)
                seconds = min(max_clip_duration, item.duration)
                total_duration += seconds
                if total_duration > audio_duration:
                    logger.info(
                        f"total duration of downloaded videos: {total_duration} seconds, skip downloading more"
                    )
                    break
        except Exception as e:
            logger.error(f"failed to download video: {utils.to_json(item)} => {str(e)}")
    logger.success(f"downloaded {len(video_paths)} videos")
    return video_paths


def download_videos_with_collector_fallback(
    task_id: str,
    search_terms: List[str],
    video_aspect: VideoAspect = VideoAspect.portrait,
    video_contact_mode: VideoConcatMode = VideoConcatMode.random,
    audio_duration: float = 0.0,
    max_clip_duration: int = 5,
) -> List[str] | List[CollectorSelectedClip]:
    fallback_source = config.app.get("collector_fallback_source", "stock") or "stock"
    legacy_fallback_enabled = _collector_enable_legacy_fallback()

    if not collector_client.check_collector_health():
        if legacy_fallback_enabled:
            logger.warning(
                f"collector unhealthy, falling back entirely to {fallback_source}"
            )
            return _download_videos_from_remote(
                task_id=task_id,
                search_terms=search_terms,
                source=fallback_source,
                video_aspect=video_aspect,
                video_contact_mode=video_contact_mode,
                audio_duration=audio_duration,
                max_clip_duration=max_clip_duration,
            )
        raise collector_client.CollectorJobFailedError(
            "COLLECTOR_UNAVAILABLE",
            "Collector service is unavailable",
        )

    try:
        return download_videos_from_collector(
            task_id=task_id,
            search_terms=search_terms,
            video_aspect=video_aspect,
            video_contact_mode=video_contact_mode,
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
        )
    except collector_client.CollectorError as exc:
        if not legacy_fallback_enabled:
            raise
        logger.warning(
            f"collector flow failed [{exc.code}], falling back to {fallback_source}: {exc.message}"
        )
        return _download_videos_from_remote(
            task_id=task_id,
            search_terms=search_terms,
            source=fallback_source,
            video_aspect=video_aspect,
            video_contact_mode=video_contact_mode,
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
        )


def save_video(video_url: str, save_dir: str = "") -> str:
    if not save_dir:
        save_dir = utils.storage_dir("cache_videos")

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    url_without_query = video_url.split("?")[0]
    url_hash = utils.md5(url_without_query)
    video_id = f"vid-{url_hash}"
    video_path = f"{save_dir}/{video_id}.mp4"

    # if video already exists, return the path
    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        logger.info(f"video already exists: {video_path}")
        return video_path

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # if video does not exist, download it
    with open(video_path, "wb") as f:
        f.write(
            requests.get(
                video_url,
                headers=headers,
                proxies=config.proxy,
                verify=_get_tls_verify(),
                timeout=(60, 240),
            ).content
        )

    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        clip = None
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            fps = clip.fps
            if duration > 0 and fps > 0:
                return video_path
        except Exception as e:
            logger.warning(f"invalid video file: {video_path} => {str(e)}")
            try:
                os.remove(video_path)
            except Exception as remove_error:
                logger.warning(
                    f"failed to remove invalid video file: {video_path}, error: {str(remove_error)}"
                )
        finally:
            if clip is not None:
                try:
                    clip.close()
                except Exception as close_error:
                    logger.warning(
                        f"failed to close video clip: {video_path}, error: {str(close_error)}"
                    )
    return ""


def download_videos(
    task_id: str,
    search_terms: List[str],
    source: str = "pexels",
    video_aspect: VideoAspect = VideoAspect.portrait,
    video_contact_mode: VideoConcatMode = VideoConcatMode.random,
    audio_duration: float = 0.0,
    max_clip_duration: int = 5,
    match_script_order: bool = False,
) -> List[str] | List[CollectorSelectedClip]:
    if source == "collector":
        return download_videos_with_collector_fallback(
            task_id=task_id,
            search_terms=search_terms,
            video_aspect=video_aspect,
            video_contact_mode=(
                VideoConcatMode.sequential
                if match_script_order
                else video_contact_mode
            ),
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
        )

    if match_script_order:
        search_videos = _get_remote_search_fn(source)
        material_directory = _resolve_material_directory(task_id)
        return _download_videos_by_script_order(
            task_id=task_id,
            search_terms=search_terms,
            search_videos=search_videos,
            video_aspect=video_aspect,
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
            material_directory=material_directory,
        )

    return _download_videos_from_remote(
        task_id=task_id,
        search_terms=search_terms,
        source=source,
        video_aspect=video_aspect,
        video_contact_mode=video_contact_mode,
        audio_duration=audio_duration,
        max_clip_duration=max_clip_duration,
    )


def _download_videos_by_script_order(
    task_id: str,
    search_terms: List[str],
    search_videos,
    video_aspect: VideoAspect,
    audio_duration: float,
    max_clip_duration: int,
    material_directory: str,
) -> List[str]:
    """
    按脚本文案顺序下载素材。

    默认下载逻辑会把所有关键词的候选素材合并成一个大列表；如果第一个
    关键词返回很多结果，最终下载时可能一直消耗这个关键词的素材，后续
    脚本主题就排不上时间线。这里按关键词分组后轮询下载：
    第 1 轮取每个关键词的第 1 个候选，第 2 轮取每个关键词的第 2 个候选。
    """
    logger.info("downloading videos with script-order material matching")
    candidate_groups = []
    valid_video_urls = set()
    found_duration = 0.0

    for search_term in search_terms:
        video_items = search_videos(
            search_term=search_term,
            minimum_duration=max_clip_duration,
            video_aspect=video_aspect,
        )
        logger.info(f"found {len(video_items)} videos for '{search_term}'")

        term_items = []
        for item in video_items:
            normalized_url = _normalize_video_url(item.url)
            if not normalized_url or normalized_url in valid_video_urls:
                continue
            term_items.append(item)
            valid_video_urls.add(normalized_url)
            found_duration += item.duration

        if term_items:
            candidate_groups.append((search_term, term_items))

    logger.info(
        f"found total ordered video candidates: {sum(len(items) for _, items in candidate_groups)}, "
        f"required duration: {audio_duration} seconds, found duration: {found_duration} seconds"
    )

    video_paths = []
    total_duration = 0.0
    candidate_index = 0
    while candidate_groups and total_duration <= audio_duration:
        has_candidate = False
        for search_term, term_items in candidate_groups:
            if candidate_index >= len(term_items):
                continue

            has_candidate = True
            item = term_items[candidate_index]
            try:
                logger.info(
                    f"downloading ordered video for '{search_term}': {item.url}"
                )
                saved_video_path = save_video(
                    video_url=item.url, save_dir=material_directory
                )
                if saved_video_path:
                    logger.info(f"video saved: {saved_video_path}")
                    video_paths.append(saved_video_path)
                    total_duration += min(max_clip_duration, item.duration)
                    if total_duration > audio_duration:
                        logger.info(
                            f"total duration of downloaded videos: {total_duration} seconds, skip downloading more"
                        )
                        break
            except Exception as e:
                logger.error(
                    f"failed to download ordered video: {utils.to_json(item)} => {str(e)}"
                )

        if not has_candidate:
            break
        candidate_index += 1

    logger.success(f"downloaded {len(video_paths)} ordered videos")
    return video_paths


if __name__ == "__main__":
    download_videos(
        "test123", ["Money Exchange Medium"], audio_duration=100, source="pixabay"
    )
