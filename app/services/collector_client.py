import json
import time
from typing import List
from urllib.parse import urlencode

import requests
from loguru import logger

from app.config import config
from app.models.schema import (
    CollectorJobError,
    CollectorJobRequest,
    CollectorJobResult,
    CollectorSelectedClip,
)


class CollectorError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class CollectorTimeoutError(CollectorError):
    pass


class CollectorJobFailedError(CollectorError):
    pass


class CollectorQuotaExceededError(CollectorError):
    pass


def _get_tls_verify() -> bool:
    tls_verify = config.app.get("tls_verify", True)
    if isinstance(tls_verify, str):
        tls_verify = tls_verify.strip().lower() not in ("0", "false", "no", "off")
    return bool(tls_verify)


def get_collector_base_url() -> str:
    return (config.app.get("collector_base_url") or "").strip().rstrip("/")


def _collector_timeout() -> float:
    try:
        return float(config.app.get("collector_timeout", 30))
    except (TypeError, ValueError):
        return 30.0


def _collector_job_timeout() -> float:
    try:
        return float(config.app.get("collector_job_timeout_seconds", 300))
    except (TypeError, ValueError):
        return 300.0


def _collector_poll_interval() -> float:
    try:
        return float(config.app.get("collector_poll_interval_seconds", 2))
    except (TypeError, ValueError):
        return 2.0


def _parse_json_response(response) -> dict | list | None:
    try:
        return response.json()
    except Exception:
        return None


def _normalize_error(
    body: dict | list | None,
    *,
    default_code: str,
    default_message: str,
) -> CollectorJobError:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return CollectorJobError(
                code=str(error.get("code") or default_code),
                message=str(error.get("message") or default_message),
            )
    return CollectorJobError(code=default_code, message=default_message)


def _normalize_stock_job_body(body: dict) -> dict:
    """Map Stock Video Collector API fields to CollectorJobResult."""
    normalized = dict(body)
    raw_error = normalized.get("error")
    if isinstance(raw_error, str):
        normalized["error"] = (
            None
            if not raw_error.strip()
            else CollectorJobError(code="COLLECTOR_JOB_FAILED", message=raw_error)
        )

    clip_items = normalized.pop("clips", None)
    selected = normalized.get("selected_clips")
    if isinstance(selected, int):
        normalized["selected_clips_count"] = selected
        normalized["selected_clips"] = clip_items if isinstance(clip_items, list) else []
    elif isinstance(selected, list):
        normalized["selected_clips_count"] = len(selected)
    elif clip_items:
        normalized["selected_clips"] = clip_items
        normalized["selected_clips_count"] = len(clip_items)

    clips = normalized.get("selected_clips") or []
    if isinstance(clips, list):
        sanitized = []
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            item = dict(clip)
            if item.get("duration") is None:
                item["duration"] = 0.0
            if item.get("width") is None:
                item["width"] = 0
            if item.get("height") is None:
                item["height"] = 0
            sanitized.append(item)
        normalized["selected_clips"] = sanitized

    return normalized


def _collector_headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


def _request_collector(
    method: str,
    path: str,
    *,
    json_payload: dict | None = None,
    expected_statuses: tuple[int, ...] = (200,),
) -> dict | list:
    base_url = get_collector_base_url()
    if not base_url:
        raise CollectorError(
            "COLLECTOR_NOT_CONFIGURED",
            "collector_base_url is not set",
        )

    url = f"{base_url}{path}"
    request_fn = requests.post if method.upper() == "POST" else requests.get

    try:
        response = request_fn(
            url,
            json=json_payload,
            headers=_collector_headers(),
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=_collector_timeout(),
        )
    except requests.RequestException as exc:
        raise CollectorError(
            "COLLECTOR_REQUEST_FAILED",
            f"Collector request failed: {exc}",
            retryable=True,
        ) from exc

    body = _parse_json_response(response)
    if response.status_code not in expected_statuses:
        error = _normalize_error(
            body,
            default_code="COLLECTOR_HTTP_ERROR",
            default_message=(
                f"Collector request failed with status {response.status_code}"
            ),
        )
        raise CollectorError(
            error.code,
            error.message,
            status_code=response.status_code,
            retryable=response.status_code >= 500,
        )

    if body is None:
        raise CollectorError(
            "COLLECTOR_INVALID_RESPONSE",
            f"Collector returned invalid JSON for {path}",
        )
    return body


def check_collector_health() -> bool:
    base_url = get_collector_base_url()
    if not base_url:
        logger.warning("collector health check skipped: collector_base_url is not set")
        return False

    try:
        response = requests.get(
            f"{base_url}/health",
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=_collector_timeout(),
        )
        if response.status_code != 200:
            logger.warning(
                f"collector health check failed: status={response.status_code}"
            )
            return False
        body = response.json()
        if isinstance(body, dict) and body.get("status") == "ok":
            return True
        logger.warning(f"collector health check failed: unexpected body={body}")
        return False
    except Exception as exc:
        logger.warning(f"collector health check failed: {exc}")
        return False


def create_stock_job(payload: CollectorJobRequest | dict) -> CollectorJobResult:
    if not isinstance(payload, CollectorJobRequest):
        payload = CollectorJobRequest(**payload)

    body = _request_collector(
        "POST",
        "/stock/jobs",
        json_payload=payload.model_dump(),
        expected_statuses=(200, 201, 202),
    )
    if not isinstance(body, dict):
        raise CollectorError(
            "COLLECTOR_INVALID_RESPONSE",
            "Collector returned invalid stock job response",
        )
    return CollectorJobResult(**_normalize_stock_job_body(body))


def get_stock_job(job_id: str) -> CollectorJobResult:
    body = _request_collector("GET", f"/stock/jobs/{job_id}")
    if not isinstance(body, dict):
        raise CollectorError(
            "COLLECTOR_INVALID_RESPONSE",
            "Collector returned invalid stock job status response",
        )
    return CollectorJobResult(**_normalize_stock_job_body(body))


def wait_for_stock_job(
    job_id: str,
    timeout: float | None = None,
    poll_interval: float | None = None,
) -> CollectorJobResult:
    timeout = _collector_job_timeout() if timeout is None else float(timeout)
    poll_interval = _collector_poll_interval() if poll_interval is None else float(
        poll_interval
    )
    deadline = time.monotonic() + max(timeout, 0.0)
    last_retryable_error: CollectorError | None = None

    while True:
        if time.monotonic() > deadline:
            raise CollectorTimeoutError(
                "COLLECTOR_TIMEOUT",
                "Timed out while waiting for stock job to finish",
                retryable=bool(last_retryable_error),
            )

        try:
            job = get_stock_job(job_id)
        except CollectorError as exc:
            if not exc.retryable:
                raise
            last_retryable_error = exc
            logger.warning(f"collector polling failed transiently: {exc.message}")
            time.sleep(max(min(poll_interval, deadline - time.monotonic()), 0))
            continue

        if job.status == "ready":
            return job
        if job.status == "failed":
            error = job.error or CollectorJobError(
                code="COLLECTOR_JOB_FAILED",
                message="Collector job failed",
            )
            raise CollectorJobFailedError(error.code, error.message)
        if job.status == "quota_exceeded":
            error = job.error or CollectorJobError(
                code="DAILY_QUOTA_EXCEEDED",
                message="Daily download quota exceeded",
            )
            raise CollectorQuotaExceededError(error.code, error.message)

        time.sleep(max(min(poll_interval, deadline - time.monotonic()), 0))


def load_selected_clips(
    response: CollectorJobResult | dict,
) -> List[CollectorSelectedClip]:
    if not isinstance(response, CollectorJobResult):
        response = CollectorJobResult(**response)

    if response.selected_clips:
        return response.selected_clips

    if not response.clips_file:
        return []

    try:
        with open(response.clips_file, "r", encoding="utf-8") as file:
            body = json.load(file)
    except Exception as exc:
        raise CollectorError(
            "COLLECTOR_CLIPS_FILE_ERROR",
            f"Failed to read collector clips file: {exc}",
        ) from exc

    if not isinstance(body, list):
        raise CollectorError(
            "COLLECTOR_INVALID_RESPONSE",
            "Collector clips file did not contain a list of selected clips",
        )
    return [CollectorSelectedClip(**clip) for clip in body if isinstance(clip, dict)]


def search_collector_clips(query: str, limit: int | None = None) -> List[dict]:
    base_url = get_collector_base_url()
    if not base_url:
        logger.warning("collector search skipped: collector_base_url is not set")
        return []

    if limit is None:
        try:
            limit = int(config.app.get("collector_search_limit", 20))
        except (TypeError, ValueError):
            limit = 20

    params = {"q": query, "limit": limit}
    query_url = f"{base_url}/clips/search?{urlencode(params)}"
    logger.info(f"searching collector clips: {query_url}")

    try:
        response = requests.get(
            query_url,
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=_collector_timeout(),
        )
        if response.status_code != 200:
            logger.error(
                f"collector search failed: status={response.status_code}, body={response.text}"
            )
            return []

        body = response.json()
        if not isinstance(body, list):
            logger.error(f"collector search failed: unexpected response={body}")
            return []
        return [hit for hit in body if isinstance(hit, dict)]
    except Exception as exc:
        logger.error(f"collector search failed: {exc}")
        return []


def fetch_collector_dashboard() -> dict:
    """Best-effort collector stats for cockpit UI (optional /stats endpoint)."""
    dashboard: dict = {
        "library_count": None,
        "library_size_tb": None,
        "quota_remaining": None,
        "worker_status": None,
    }
    base_url = get_collector_base_url()
    if not base_url:
        return dashboard

    try:
        body = _request_collector("GET", "/stats")
        if isinstance(body, dict):
            dashboard["library_count"] = body.get("library_count") or body.get("total_clips")
            dashboard["library_size_tb"] = body.get("library_size_tb") or body.get("total_tb")
            dashboard["quota_remaining"] = body.get("quota_remaining") or body.get("quota")
            dashboard["worker_status"] = body.get("worker_status") or body.get("worker")
    except CollectorError:
        pass
    except Exception as exc:
        logger.debug(f"collector dashboard unavailable: {exc}")

    if dashboard["worker_status"] is None and check_collector_health():
        dashboard["worker_status"] = "Idle"

    return dashboard
