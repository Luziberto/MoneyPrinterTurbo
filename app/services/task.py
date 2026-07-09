import math
import os.path
import time
from os import path

from loguru import logger

from app.config import config
from app.models import const
from app.models.schema import (
    CollectorSelectedClip,
    VideoConcatMode,
    VideoParams,
    collector_keywords_to_strings,
    normalize_collector_keywords,
)
from app.services import collector_client, llm, material, publish, subtitle, twelvelabs, video, voice
from app.services import state as sm
from app.services.runtime_limits import cap_thread_count
from app.utils import utils


def generate_script(task_id, params):
    logger.info("\n\n## generating video script")
    script_mode = getattr(params, "script_mode", None)
    manual_script = params.video_script.strip()

    if script_mode == "polish":
        if not manual_script:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("polish mode requires a non-empty brief in video_script")
            return None
        params.script_brief = manual_script
        try:
            video_script = llm.polish_script(
                brief=manual_script,
                video_subject=params.video_subject,
                duration_seconds=max(30, params.paragraph_number * 25),
                language=params.video_language or "",
            )
        except ValueError as exc:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(f"polish script failed: {exc}")
            return None
        return video_script

    if manual_script and script_mode != "auto":
        logger.debug(f"video script: \n{manual_script}")
        return manual_script

    if manual_script and script_mode is None:
        logger.debug(f"video script: \n{manual_script}")
        return manual_script

    video_script = llm.generate_script(
        video_subject=params.video_subject,
        language=params.video_language,
        paragraph_number=params.paragraph_number,
        video_script_prompt=params.video_script_prompt,
        custom_system_prompt=params.custom_system_prompt,
    )

    if not video_script:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        logger.error("failed to generate video script.")
        return None

    return video_script


def generate_terms(task_id, params, video_script):
    logger.info("\n\n## generating video terms")
    video_terms = params.video_terms
    has_explicit_weights = False
    if not video_terms:
        generated = llm.generate_terms(
            video_subject=params.video_subject,
            video_script=video_script,
            amount=llm.default_terms_amount(
                params.match_materials_to_script,
                params.paragraph_number,
            ),
            match_script_order=params.match_materials_to_script,
            paragraph_number=params.paragraph_number,
        )
        if isinstance(generated, str):
            return generated
        video_terms = [keyword.model_dump() for keyword in generated.keywords]
        has_explicit_weights = generated.has_explicit_weights
    else:
        normalized = normalize_collector_keywords(video_terms)
        video_terms = [keyword.model_dump() for keyword in normalized.keywords]
        has_explicit_weights = normalized.has_explicit_weights
        logger.debug(f"video terms: {utils.to_json(video_terms)}")

    if (
        not params.match_materials_to_script
        and not has_explicit_weights
        and video_terms
    ):
        reranked_terms = twelvelabs.rerank_terms_by_subject(
            params.video_subject, collector_keywords_to_strings(video_terms)
        )
        packages_by_term = {
            keyword["term"]: keyword
            for keyword in video_terms
            if isinstance(keyword, dict) and keyword.get("term")
        }
        video_terms = [
            packages_by_term[term] for term in reranked_terms if term in packages_by_term
        ]

    if not video_terms:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        logger.error("failed to generate video terms.")
        return None

    return video_terms


def save_script_data(task_id, video_script, video_terms, params):
    script_file = path.join(utils.task_dir(task_id), "script.json")
    script_data = {
        "script": video_script,
        "search_terms": video_terms,
        "params": params,
    }

    with open(script_file, "w", encoding="utf-8") as f:
        f.write(utils.to_json(script_data))


def generate_audio(task_id, params, video_script):
    '''
    Generate audio for the video script.
    If a custom audio file is provided, it will be used directly.
    There will be no subtitle maker object returned in this case.
    Otherwise, TTS will be used to generate the audio.
    Returns:
        - audio_file: path to the generated or provided audio file
        - audio_duration: duration of the audio in seconds
        - sub_maker: subtitle maker object if TTS is used, None otherwise
    '''
    logger.info("\n\n## generating audio")
    # /audio 和 /subtitle 请求模型不包含 custom_audio_file，
    # 这里统一做兼容读取，避免直调接口时抛属性错误。
    custom_audio_file = getattr(params, "custom_audio_file", None)
    if not custom_audio_file or not os.path.exists(custom_audio_file):
        if custom_audio_file:
            logger.warning(
                f"custom audio file not found: {custom_audio_file}, using TTS to generate audio."
            )
        else:
            logger.info("no custom audio file provided, using TTS to generate audio.")
        audio_file = path.join(utils.task_dir(task_id), "audio.mp3")
        sub_maker = voice.tts(
            text=video_script,
            voice_name=voice.parse_voice_name(params.voice_name),
            voice_rate=params.voice_rate,
            voice_file=audio_file,
        )
        if sub_maker is None:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(
                """failed to generate audio:
1. check if the language of the voice matches the language of the video script.
2. check if the network is available. If you are in China, it is recommended to use a VPN and enable the global traffic mode.
            """.strip()
            )
            return None, None, None
        audio_duration = math.ceil(voice.get_audio_duration(sub_maker))
        if audio_duration == 0:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("failed to get audio duration.")
            return None, None, None
        return audio_file, audio_duration, sub_maker
    else:
        logger.info(f"using custom audio file: {custom_audio_file}")
        audio_duration = voice.get_audio_duration(custom_audio_file)
        if audio_duration == 0:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("failed to get audio duration from custom audio file.")
            return None, None, None
        return custom_audio_file, audio_duration, None

def generate_subtitle(task_id, params, video_script, sub_maker, audio_file):
    '''
    Generate subtitle for the video script.
    If subtitle generation is disabled or no subtitle maker is provided, it will return an empty string.
    Otherwise, it will generate the subtitle using the specified provider.
    Returns:
        - subtitle_path: path to the generated subtitle file
    '''
    logger.info("\n\n## generating subtitle")
    if not params.subtitle_enabled or sub_maker is None:
        return ""

    subtitle_path = path.join(utils.task_dir(task_id), "subtitle.srt")
    subtitle_provider = config.app.get("subtitle_provider", "edge").strip().lower()
    logger.info(f"\n\n## generating subtitle, provider: {subtitle_provider}")

    subtitle_fallback = False
    if subtitle_provider == "edge":
        voice.create_subtitle(
            text=video_script, sub_maker=sub_maker, subtitle_file=subtitle_path
        )
        if not os.path.exists(subtitle_path):
            subtitle_fallback = True
            logger.warning("subtitle file not found, fallback to whisper")

    if subtitle_provider == "whisper" or subtitle_fallback:
        subtitle.create(audio_file=audio_file, subtitle_file=subtitle_path)
        logger.info("\n\n## correcting subtitle")
        subtitle.correct(subtitle_file=subtitle_path, video_script=video_script)

    subtitle_lines = subtitle.file_to_subtitles(subtitle_path)
    if not subtitle_lines:
        logger.warning(f"subtitle file is invalid: {subtitle_path}")
        return ""

    return subtitle_path


def _serialize_materials_for_state(materials):
    if not isinstance(materials, list):
        return materials
    serialized = []
    for item in materials:
        if isinstance(item, CollectorSelectedClip):
            serialized.append(item.model_dump())
        else:
            serialized.append(item)
    return serialized


def get_video_materials(task_id, params, video_terms, audio_duration):
    if params.video_source == "local":
        logger.info("\n\n## preprocess local materials")
        materials = video.preprocess_video(
            materials=params.video_materials, clip_duration=params.video_clip_duration
        )
        if not materials:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(
                "no valid materials found, please check the materials and try again."
            )
            return None
        return [material_info.url for material_info in materials]
    else:
        logger.info(f"\n\n## downloading videos from {params.video_source}")
        try:
            downloaded_videos = material.download_videos(
                task_id=task_id,
                search_terms=video_terms,
                source=params.video_source,
                video_aspect=params.video_aspect,
                video_contact_mode=(
                    VideoConcatMode.sequential
                    if params.match_materials_to_script
                    else params.video_concat_mode
                ),
                audio_duration=audio_duration * params.video_count,
                max_clip_duration=params.video_clip_duration,
                match_script_order=params.match_materials_to_script,
                collector_target_clips=params.collector_target_clips,
                collector_min_acceptable_clips=params.collector_min_acceptable_clips,
            )
        except collector_client.CollectorError as exc:
            sm.state.update_task(
                task_id,
                state=const.TASK_STATE_FAILED,
                error={"code": exc.code, "message": exc.message},
            )
            logger.error(f"collector flow failed [{exc.code}]: {exc.message}")
            return None
        if not downloaded_videos:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(
                "failed to download videos, maybe the network is not available. if you are in China, please use a VPN."
            )
            return None
        return downloaded_videos


def generate_final_videos(
    task_id, params, downloaded_videos, audio_file, subtitle_path
):
    final_video_paths = []
    combined_video_paths = []
    if params.match_materials_to_script:
        video_concat_mode = VideoConcatMode.sequential
    elif params.video_count == 1:
        video_concat_mode = params.video_concat_mode
    else:
        video_concat_mode = VideoConcatMode.random
    video_transition_mode = params.video_transition_mode

    _progress = 50
    for i in range(params.video_count):
        index = i + 1
        combined_video_path = path.join(
            utils.task_dir(task_id), f"combined-{index}.mp4"
        )
        logger.info(f"\n\n## combining video: {index} => {combined_video_path}")
        video.combine_videos(
            combined_video_path=combined_video_path,
            video_paths=downloaded_videos,
            audio_file=audio_file,
            video_aspect=params.video_aspect,
            video_concat_mode=video_concat_mode,
            video_transition_mode=video_transition_mode,
            max_clip_duration=params.video_clip_duration,
            threads=params.n_threads,
        )

        _progress += 50 / params.video_count / 2
        sm.state.update_task(task_id, progress=_progress)

        final_video_path = path.join(utils.task_dir(task_id), f"final-{index}.mp4")

        logger.info(f"\n\n## generating video: {index} => {final_video_path}")
        video.generate_video(
            video_path=combined_video_path,
            audio_path=audio_file,
            subtitle_path=subtitle_path,
            output_file=final_video_path,
            params=params,
        )

        _progress += 50 / params.video_count / 2
        sm.state.update_task(task_id, progress=_progress)

        final_video_paths.append(final_video_path)
        combined_video_paths.append(combined_video_path)

    return final_video_paths, combined_video_paths


def _stage_timer(task_id: str, stop_at: str):
    """Yields a callable that records a video_events stage_completed row when
    stop_at == "video" (i.e. only for tasks that actually got a Video Library
    row created in app/controllers/v1/video.py::create_task -- recording
    stage timing for a script/terms/audio-only task would leave a dangling
    event pointing at a video row that was never created).
    """
    stage_start = time.monotonic()

    def _mark(stage: str) -> None:
        nonlocal stage_start
        if stop_at == "video":
            from app.services.video_library_transitions import record_stage_event

            record_stage_event(task_id, stage, stage_start)
        stage_start = time.monotonic()

    return _mark


def start(task_id, params: VideoParams, stop_at: str = "video"):
    logger.info(f"start task: {task_id}, stop_at: {stop_at}")
    params.n_threads = cap_thread_count(params.n_threads)
    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=5)
    _mark_stage = _stage_timer(task_id, stop_at)

    # 1. Generate script
    video_script = generate_script(task_id, params)
    if not video_script or "Error: " in video_script:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return
    _mark_stage("script")

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=10)

    if stop_at == "script":
        sm.state.update_task(
            task_id, state=const.TASK_STATE_COMPLETE, progress=100, script=video_script
        )
        return {"script": video_script}

    # 2. Generate terms
    video_terms = ""
    if params.video_source != "local":
        video_terms = generate_terms(task_id, params, video_script)
        if not video_terms:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            return

    save_script_data(task_id, video_script, video_terms, params)
    _mark_stage("terms")

    if stop_at == "terms":
        sm.state.update_task(
            task_id, state=const.TASK_STATE_COMPLETE, progress=100, terms=video_terms
        )
        return {"script": video_script, "terms": video_terms}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=20)

    # 3. Generate audio
    audio_file, audio_duration, sub_maker = generate_audio(
        task_id, params, video_script
    )
    if not audio_file:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=30)
    _mark_stage("tts")

    if stop_at == "audio":
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            audio_file=audio_file,
        )
        return {"audio_file": audio_file, "audio_duration": audio_duration}

    # 4. Generate subtitle
    subtitle_path = generate_subtitle(
        task_id, params, video_script, sub_maker, audio_file
    )

    if stop_at == "subtitle":
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            subtitle_path=subtitle_path,
        )
        return {"subtitle_path": subtitle_path}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=40)

    # 5. Get video materials
    downloaded_videos = get_video_materials(
        task_id, params, video_terms, audio_duration
    )
    if not downloaded_videos:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return
    _mark_stage("collector")

    if stop_at == "materials":
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            materials=_serialize_materials_for_state(downloaded_videos),
        )
        return {"materials": downloaded_videos}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=50)

    # 仅完整视频生成流程才需要处理视频拼接模式；
    # 这样可以避免 /subtitle 和 /audio 这类请求访问不存在的字段。
    if type(params.video_concat_mode) is str:
        params.video_concat_mode = VideoConcatMode(params.video_concat_mode)

    # 6. Generate final videos
    final_video_paths, combined_video_paths = generate_final_videos(
        task_id, params, downloaded_videos, audio_file, subtitle_path
    )

    if not final_video_paths:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return
    _mark_stage("render")

    thumbnail_path, video_duration_seconds, video_file_size_bytes = _extract_thumbnail_and_stats(
        task_id, final_video_paths[0]
    )

    logger.success(
        f"task {task_id} finished, generated {len(final_video_paths)} videos."
    )

    # 7. Cross-post to social platforms (if auto_upload enabled)
    publish_platforms = getattr(params, "publish_platforms", None)
    cross_post_results = publish.cross_post_if_auto_upload(
        video_paths=final_video_paths,
        subject=params.video_subject or "",
        script=video_script or "",
        language=params.video_language or "",
        publish_platforms=publish_platforms,
    )
    _mark_stage("upload")

    kwargs = {
        "videos": final_video_paths,
        "combined_videos": combined_video_paths,
        "script": video_script,
        "terms": video_terms,
        "audio_file": audio_file,
        "audio_duration": audio_duration,
        "subtitle_path": subtitle_path,
        "materials": _serialize_materials_for_state(downloaded_videos),
        "cross_post_results": cross_post_results if cross_post_results else None,
        "thumbnail_path": thumbnail_path,
        "video_duration_seconds": video_duration_seconds,
        "video_file_size_bytes": video_file_size_bytes,
    }
    sm.state.update_task(
        task_id, state=const.TASK_STATE_COMPLETE, progress=100, **kwargs
    )
    return kwargs


def _extract_thumbnail_and_stats(task_id: str, video_path: str):
    """Best-effort thumbnail + duration/size capture for the Video Library.
    Never raises -- a failure here must not fail an otherwise-successful render.
    """
    from app.services import thumbnail as thumbnail_service

    thumb_path = path.join(utils.task_dir(task_id), "final-1-thumbnail.jpg")
    thumbnail_ok = thumbnail_service.extract_thumbnail(video_path, thumb_path)

    file_size_bytes = None
    try:
        file_size_bytes = os.path.getsize(video_path)
    except OSError as exc:
        logger.warning(f"failed to stat final video for {task_id}: {exc}")

    duration_seconds = None
    try:
        from moviepy import VideoFileClip

        with VideoFileClip(video_path) as clip:
            duration_seconds = clip.duration
    except Exception as exc:  # noqa: BLE001 - best-effort, must not fail the render
        logger.warning(f"failed to read video duration for {task_id}: {exc}")

    return (thumb_path if thumbnail_ok else None), duration_seconds, file_size_bytes


def start_with_lock(task_id, params: VideoParams, stop_at: str = "video"):
    """Single-flight-locked entry point for full renders (stop_at == "video").

    Both pipeline's POST /videos and the cockpit's POST /cockpit/render go
    through this (see app/controllers/v1/video.py::create_task) so a manual
    cockpit render and a pipeline batch job can never run concurrently.
    `/subtitle` and `/audio` still call start() directly -- they're cheap and
    were never covered by this lock in the Streamlit cockpit either.

    Registered by name (not passed as a closure) so RedisTaskManager can
    serialize it into its queue via FUNC_MAP; see
    app/controllers/manager/redis_manager.py.
    """
    if stop_at != "video":
        return start(task_id=task_id, params=params, stop_at=stop_at)

    from app.services.runtime_limits import (
        GenerationAlreadyRunningError,
        single_flight_generation_lock,
    )

    try:
        with single_flight_generation_lock(task_id):
            return start(task_id=task_id, params=params, stop_at=stop_at)
    except GenerationAlreadyRunningError as exc:
        logger.warning(f"task {task_id} rejected: generation already running ({exc})")
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_FAILED,
            error=f"Another generation is already running (task {exc})",
        )
        return None


def start_and_track_library(task_id, params: VideoParams, stop_at: str = "video"):
    """Wraps start_with_lock() and syncs the Video Library row (created at
    submission by app/controllers/v1/video.py::create_task) to the task's
    final state. Runs strictly after start_with_lock() returns, so the
    single-flight lock behavior is completely unaffected by this.

    Only used for stop_at == "video" (see create_task) -- /subtitle and
    /audio keep calling start_with_lock directly, since no library row
    exists for those.
    """
    try:
        return start_with_lock(task_id=task_id, params=params, stop_at=stop_at)
    finally:
        _sync_video_library_from_task_state(task_id)


def _sync_video_library_from_task_state(task_id: str) -> None:
    try:
        from app.services.video_library_store import VideoLibraryStore
        from app.services.video_library_transitions import mark_failed, mark_ready

        task = sm.state.get_task(task_id)
        if not task:
            return

        store = VideoLibraryStore()
        if not store.get_video(task_id):
            return

        state = task.get("state")
        if state == const.TASK_STATE_COMPLETE:
            # `terms` is normally list[dict] (see generate_terms()) but can be
            # a raw error string in a pre-existing upstream edge case -- guard
            # so the library's `keywords` column never gets a non-list value.
            terms = task.get("terms")
            mark_ready(
                store,
                task_id,
                thumbnail_path=task.get("thumbnail_path"),
                video_path=(task.get("videos") or [None])[0],
                duration_seconds=task.get("video_duration_seconds"),
                file_size_bytes=task.get("video_file_size_bytes"),
                keywords=terms if isinstance(terms, list) else None,
            )
        elif state == const.TASK_STATE_FAILED:
            mark_failed(store, task_id, error=task.get("error"))
    except Exception as exc:  # noqa: BLE001 - must never mask the render's own result
        logger.warning(f"failed to sync video-library row for task {task_id}: {exc}")


if __name__ == "__main__":
    task_id = "task_id"
    params = VideoParams(
        video_subject="金钱的作用",
        voice_name="zh-CN-XiaoyiNeural-Female",
        voice_rate=1.0,
    )
    start(task_id, params, stop_at="video")
