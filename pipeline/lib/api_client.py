"""HTTP client for MoneyPrinterTurbo API (no API keys — uses server config.toml)."""

from __future__ import annotations

import time
from typing import Any

import requests

TASK_STATE_FAILED = -1
TASK_STATE_COMPLETE = 1


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(
        self,
        base_url: str,
        poll_interval: float = 5.0,
        poll_timeout: float = 1800.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    def _unwrap(self, response: requests.Response) -> Any:
        response.raise_for_status()
        body = response.json()
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body

    def create_video(self, payload: dict) -> str:
        url = f"{self.base_url}/api/v1/videos"
        data = self._unwrap(requests.post(url, json=payload, timeout=60))
        task_id = data.get("task_id") if isinstance(data, dict) else None
        if not task_id:
            raise ApiError(f"API did not return task_id: {data}")
        return task_id

    def get_task(self, task_id: str) -> dict:
        url = f"{self.base_url}/api/v1/tasks/{task_id}"
        data = self._unwrap(requests.get(url, timeout=30))
        if not isinstance(data, dict):
            raise ApiError(f"Unexpected task response: {data}")
        return data

    def wait_for_task(self, task_id: str) -> dict:
        deadline = time.time() + self.poll_timeout
        while time.time() < deadline:
            task = self.get_task(task_id)
            state = task.get("state")
            if state == TASK_STATE_COMPLETE:
                return task
            if state == TASK_STATE_FAILED:
                raise ApiError(f"Task {task_id} failed (state={state})")
            time.sleep(self.poll_interval)
        raise ApiError(f"Timeout waiting for task {task_id}")
