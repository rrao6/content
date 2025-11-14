"""Production monitoring and alerting for poster analysis."""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class AnalysisMetrics:
    """Metrics for analysis performance and reliability."""
    
    # Counters
    total_requests: int = 0
    successful_analyses: int = 0
    cache_hits: int = 0
    download_failures: int = 0
    api_failures: int = 0
    parsing_failures: int = 0
    
    # Timing
    total_duration_ms: float = 0.0
    download_duration_ms: float = 0.0
    api_duration_ms: float = 0.0
    
    # Error tracking
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    recent_errors: List[Dict[str, Any]] = field(default_factory=list)
    
    # Rate tracking
    requests_per_minute: List[float] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_analyses / self.total_requests
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests
    
    @property
    def average_duration_ms(self) -> float:
        """Calculate average request duration."""
        if self.total_requests == 0:
            return 0.0
        return self.total_duration_ms / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging/monitoring."""
        return {
            "total_requests": self.total_requests,
            "successful_analyses": self.successful_analyses,
            "success_rate": self.success_rate,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": self.cache_hit_rate,
            "download_failures": self.download_failures,
            "api_failures": self.api_failures,
            "parsing_failures": self.parsing_failures,
            "average_duration_ms": self.average_duration_ms,
            "error_counts": dict(self.error_counts),
            "recent_error_count": len(self.recent_errors),
        }


class AnalysisMonitor:
    """Monitor and alert on analysis pipeline health."""
    
    def __init__(
        self,
        alert_threshold_error_rate: float = 0.2,  # Alert if >20% errors
        alert_threshold_duration_ms: float = 5000,  # Alert if >5s average
        alert_threshold_rpm: int = 100,  # Alert if >100 requests/min
        window_size_minutes: int = 5,
    ):
        self.alert_threshold_error_rate = alert_threshold_error_rate
        self.alert_threshold_duration_ms = alert_threshold_duration_ms
        self.alert_threshold_rpm = alert_threshold_rpm
        self.window_size_minutes = window_size_minutes
        
        self.metrics = AnalysisMetrics()
        self._start_time = time.time()
        self._window_start = time.time()
        self._window_metrics = AnalysisMetrics()
        
    def record_request_start(self) -> float:
        """Record the start of a request and return start time."""
        self.metrics.total_requests += 1
        self._window_metrics.total_requests += 1
        return time.time()
    
    def record_request_end(
        self,
        start_time: float,
        success: bool,
        cache_hit: bool = False,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Record the end of a request with its outcome."""
        duration_ms = (time.time() - start_time) * 1000
        self.metrics.total_duration_ms += duration_ms
        self._window_metrics.total_duration_ms += duration_ms
        
        if success:
            self.metrics.successful_analyses += 1
            self._window_metrics.successful_analyses += 1
        
        if cache_hit:
            self.metrics.cache_hits += 1
            self._window_metrics.cache_hits += 1
        
        if error_type:
            self.metrics.error_counts[error_type] += 1
            self._window_metrics.error_counts[error_type] += 1
            
            # Track recent errors for debugging
            error_record = {
                "timestamp": datetime.now().isoformat(),
                "type": error_type,
                "message": error_message,
                "duration_ms": duration_ms,
            }
            self.metrics.recent_errors.append(error_record)
            # Keep only last 100 errors
            if len(self.metrics.recent_errors) > 100:
                self.metrics.recent_errors = self.metrics.recent_errors[-100:]
        
        # Check if we should rotate the window
        self._check_window_rotation()
        
        # Check alerts
        self._check_alerts()
    
    def record_download_duration(self, duration_ms: float) -> None:
        """Record image download duration."""
        self.metrics.download_duration_ms += duration_ms
        self._window_metrics.download_duration_ms += duration_ms
    
    def record_api_duration(self, duration_ms: float) -> None:
        """Record API call duration."""
        self.metrics.api_duration_ms += duration_ms
        self._window_metrics.api_duration_ms += duration_ms
    
    def _check_window_rotation(self) -> None:
        """Check if we should start a new metrics window."""
        current_time = time.time()
        window_duration = current_time - self._window_start
        
        if window_duration >= self.window_size_minutes * 60:
            # Log window metrics
            logger.info(
                "metrics_window_complete",
                window_duration_seconds=window_duration,
                metrics=self._window_metrics.to_dict(),
            )
            
            # Reset window
            self._window_start = current_time
            self._window_metrics = AnalysisMetrics()
    
    def _check_alerts(self) -> None:
        """Check if any alerts should be triggered."""
        # Error rate alert
        if self._window_metrics.total_requests > 10:  # Need minimum requests
            error_rate = 1.0 - self._window_metrics.success_rate
            if error_rate > self.alert_threshold_error_rate:
                logger.error(
                    "ALERT_high_error_rate",
                    error_rate=error_rate,
                    threshold=self.alert_threshold_error_rate,
                    window_metrics=self._window_metrics.to_dict(),
                )
        
        # Duration alert
        if self._window_metrics.average_duration_ms > self.alert_threshold_duration_ms:
            logger.error(
                "ALERT_high_latency",
                average_duration_ms=self._window_metrics.average_duration_ms,
                threshold_ms=self.alert_threshold_duration_ms,
            )
        
        # Rate limit alert
        current_rpm = self._calculate_current_rpm()
        if current_rpm > self.alert_threshold_rpm:
            logger.error(
                "ALERT_high_request_rate",
                current_rpm=current_rpm,
                threshold_rpm=self.alert_threshold_rpm,
            )
    
    def _calculate_current_rpm(self) -> float:
        """Calculate current requests per minute."""
        window_duration_minutes = (time.time() - self._window_start) / 60
        if window_duration_minutes == 0:
            return 0.0
        return self._window_metrics.total_requests / window_duration_minutes
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status for monitoring dashboards."""
        current_rpm = self._calculate_current_rpm()
        uptime_seconds = time.time() - self._start_time
        
        return {
            "status": self._determine_health_status(),
            "uptime_seconds": uptime_seconds,
            "all_time_metrics": self.metrics.to_dict(),
            "window_metrics": self._window_metrics.to_dict(),
            "current_rpm": current_rpm,
            "alerts": self._get_active_alerts(),
        }
    
    def _determine_health_status(self) -> str:
        """Determine overall health status."""
        if self._window_metrics.total_requests == 0:
            return "idle"
        
        error_rate = 1.0 - self._window_metrics.success_rate
        if error_rate > self.alert_threshold_error_rate:
            return "unhealthy"
        elif error_rate > self.alert_threshold_error_rate / 2:
            return "degraded"
        else:
            return "healthy"
    
    def _get_active_alerts(self) -> List[str]:
        """Get list of currently active alerts."""
        alerts = []
        
        if self._window_metrics.total_requests > 10:
            error_rate = 1.0 - self._window_metrics.success_rate
            if error_rate > self.alert_threshold_error_rate:
                alerts.append(f"high_error_rate ({error_rate:.2%})")
        
        if self._window_metrics.average_duration_ms > self.alert_threshold_duration_ms:
            alerts.append(f"high_latency ({self._window_metrics.average_duration_ms:.0f}ms)")
        
        current_rpm = self._calculate_current_rpm()
        if current_rpm > self.alert_threshold_rpm:
            alerts.append(f"high_request_rate ({current_rpm:.0f} rpm)")
        
        return alerts


# Global monitor instance
_monitor: Optional[AnalysisMonitor] = None


def get_analysis_monitor() -> AnalysisMonitor:
    """Get or create the global analysis monitor."""
    global _monitor
    if _monitor is None:
        _monitor = AnalysisMonitor()
    return _monitor
