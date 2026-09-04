"""Lightweight in-process background task queue for administrative jobs."""

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from threading import Lock
from typing import Callable, Dict, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class BackgroundTaskManager:
    """Run administrative jobs off the request event loop.

    A single worker keeps SQLite writes ordered and avoids multiple large imports
    competing for the same database lock. Task metadata is intentionally kept in
    memory because this is a small, single-process administrative queue.
    """

    def __init__(self, max_tasks: int = 100):
        self._tasks: "OrderedDict[str, dict]" = OrderedDict()
        self._futures: Dict[str, object] = {}
        self._lock = Lock()
        self._max_tasks = max_tasks
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lab-booking-task")

    def submit(
        self,
        task_type: str,
        title: str,
        total: int,
        metadata: Optional[dict],
        worker: Callable[[Callable[[int, int, Optional[str]], None]], dict],
    ) -> dict:
        task_id = f"task_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
        task = {
            "id": task_id,
            "type": task_type,
            "title": title,
            "status": "queued",
            "current": 0,
            "total": max(total, 0),
            "percent": 0,
            "message": "任务已建立，等待后台处理",
            "metadata": metadata or {},
            "result": None,
            "error": None,
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
        }
        with self._lock:
            self._tasks[task_id] = task
            self._prune_locked()
        try:
            future = self._executor.submit(self._run, task_id, worker)
            with self._lock:
                self._futures[task_id] = future
        except Exception as exc:
            self._update(task_id, status="failed", error=str(exc), message="后台任务提交失败", finished_at=_now())
        return self.get(task_id)

    def _run(self, task_id: str, worker: Callable) -> None:
        self._update(task_id, status="running", started_at=_now(), message="正在处理")

        def progress(current: int, total: int, message: Optional[str] = None) -> None:
            total = max(total, 0)
            percent = 100 if total == 0 and current > 0 else (round(current * 100 / total) if total else 0)
            self._update(
                task_id,
                current=max(current, 0),
                total=total,
                percent=min(max(percent, 0), 100),
                message=message or "正在处理",
            )

        try:
            result = worker(progress) or {}
        except Exception as exc:
            self._update(
                task_id,
                status="failed",
                error=str(exc),
                message="任务执行失败",
                finished_at=_now(),
            )
            with self._lock:
                self._futures.pop(task_id, None)
            return

        self._update(
            task_id,
            status="completed",
            current=self._tasks[task_id]["total"],
            percent=100,
            message=result.get("message", "任务已完成"),
            result=result,
            finished_at=_now(),
        )
        with self._lock:
            self._futures.pop(task_id, None)

    def _update(self, task_id: str, **changes) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is not None:
                task.update(changes)

    def _prune_locked(self) -> None:
        if len(self._tasks) <= self._max_tasks:
            return
        for task_id, task in list(self._tasks.items()):
            if task["status"] in ("completed", "failed", "cancelled"):
                self._tasks.pop(task_id, None)
                if len(self._tasks) <= self._max_tasks:
                    break

    def get(self, task_id: str) -> Optional[dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            return deepcopy(task) if task else None

    def cancel(self, task_id: str) -> Optional[dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            future = self._futures.get(task_id)
            if not task:
                return None
            if task["status"] != "queued" or future is None or not future.cancel():
                return deepcopy(task)
            task.update({
                "status": "cancelled",
                "message": "任务已取消",
                "finished_at": _now(),
            })
            self._futures.pop(task_id, None)
            return deepcopy(task)

    def list(self) -> list:
        with self._lock:
            return [deepcopy(task) for task in reversed(self._tasks.values())]


task_manager = BackgroundTaskManager()
