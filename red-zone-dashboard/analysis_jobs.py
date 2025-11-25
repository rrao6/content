"""Background job management for dashboard-triggered analyses."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from analyzer import run_dashboard_analysis


class AnalysisJob:
    """Tracks state for a dashboard-triggered analysis."""

    MAX_LOG_ENTRIES = 100

    def __init__(self, params: Dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.params = params
        self.status = "pending"
        self.processed = 0
        self.total = params.get("limit")
        self.success = 0
        self.errors = 0
        self.run_id: Optional[int] = None
        self.error: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.logs: list[Dict[str, str]] = []
        self._lock = threading.Lock()

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "job_id": self.id,
                "status": self.status,
                "processed": self.processed,
                "total": self.total,
                "success": self.success,
                "errors": self.errors,
                "run_id": self.run_id,
                "error": self.error,
                "created_at": self.created_at.isoformat(),
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "logs": list(self.logs),
            }

    def add_log(self, message: str) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
        }
        with self._lock:
            self.logs.append(entry)
            if len(self.logs) > self.MAX_LOG_ENTRIES:
                self.logs = self.logs[-self.MAX_LOG_ENTRIES:]

    def update_from_progress(self, update: Dict[str, Any]) -> None:
        message = update.get("message")
        with self._lock:
            if "processed" in update:
                self.processed = update["processed"]
            if "success" in update:
                self.success = update["success"]
            if "errors" in update:
                self.errors = update["errors"]
            if update.get("total") is not None:
                self.total = update.get("total")
        if message:
            self.add_log(message)

    def start(self) -> None:
        with self._lock:
            self.status = "running"
            self.started_at = datetime.utcnow()
        self.add_log("Analysis job started.")

    def mark_completed(self, run_id: int, totals: Dict[str, Any]) -> None:
        with self._lock:
            self.status = "completed"
            self.run_id = run_id
            self.completed_at = datetime.utcnow()
            self.success = totals.get("passed", self.success)
            self.errors = totals.get("failed", self.errors)
            self.processed = totals.get("total", self.processed)
            if totals.get("total") and not self.total:
                self.total = totals["total"]
        self.add_log("Analysis completed successfully.")

    def mark_failed(self, error_message: str) -> None:
        with self._lock:
            self.status = "failed"
            self.error = error_message
            self.completed_at = datetime.utcnow()
        self.add_log(f"Analysis failed: {error_message}")


_JOB_LOCK = threading.Lock()
_JOBS: Dict[str, AnalysisJob] = {}


def start_analysis_job(params: Dict[str, Any]) -> AnalysisJob:
    """Create and start a background analysis job."""
    job = AnalysisJob(params=params)
    with _JOB_LOCK:
        _JOBS[job.id] = job

    thread = threading.Thread(target=_run_job, args=(job,), daemon=True)
    thread.start()
    return job


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Return serialized status for a job."""
    with _JOB_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        return None
    return job.to_dict()


def get_latest_active_job() -> Optional[Dict[str, Any]]:
    """Get the latest active (running) job."""
    with _JOB_LOCK:
        for job_id in sorted(_JOBS.keys(), reverse=True):
            job = _JOBS[job_id]
            if job.status == 'running':
                return job.to_dict()
    return None


def _run_job(job: AnalysisJob) -> None:
    """Worker that executes the analysis and tracks progress."""
    job.start()

    def progress_callback(update: Dict[str, Any]) -> None:
        job.update_from_progress(update)

    try:
        result = run_dashboard_analysis(
            progress_callback=progress_callback,
            **job.params,
        )
        if result.get("status") == "success":
            job.mark_completed(run_id=result.get("run_id"), totals=result)
        else:
            job.mark_failed(result.get("message", "Analysis failed"))
    except Exception as exc:
        job.mark_failed(str(exc))

