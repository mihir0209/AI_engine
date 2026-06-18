"""
Structured logging module for AI Engine
JSON-formatted logs with context and SLA monitoring
"""
import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import threading


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: str
    level: str
    message: str
    module: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAMetric:
    """SLA monitoring metric"""
    name: str
    target: float  # e.g., 99.9 for availability, 2000 for latency ms
    current: float = 0.0
    window_minutes: int = 60
    breaches: int = 0
    last_breach: Optional[str] = None


class StructuredLogger:
    """JSON structured logging"""

    def __init__(self, log_dir: str = "logs", log_level: str = "INFO"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_level = log_level
        self._lock = threading.Lock()
        self._buffer: List[LogEntry] = []
        self._buffer_size = 100

    def _get_log_file(self) -> str:
        """Get current log file path"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"app_{date_str}.jsonl")

    def _should_log(self, level: str) -> bool:
        """Check if message should be logged"""
        levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
        return levels.get(level, 0) >= levels.get(self.log_level, 1)

    def log(self, level: str, message: str, **kwargs):
        """Log a message"""
        if not self._should_log(level):
            return

        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            message=message,
            module=kwargs.get("module", "unknown"),
            request_id=kwargs.get("request_id"),
            user_id=kwargs.get("user_id"),
            tenant_id=kwargs.get("tenant_id"),
            provider=kwargs.get("provider"),
            model=kwargs.get("model"),
            duration_ms=kwargs.get("duration_ms"),
            status_code=kwargs.get("status_code"),
            error=kwargs.get("error"),
            metadata=kwargs.get("metadata", {})
        )

        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self._buffer_size:
                self._flush()

    def _flush(self):
        """Flush buffer to disk"""
        if not self._buffer:
            return

        log_file = self._get_log_file()
        with open(log_file, "a") as f:
            for entry in self._buffer:
                f.write(json.dumps(entry.__dict__) + "\n")
        self._buffer.clear()

    def info(self, message: str, **kwargs):
        """Log info message"""
        self.log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self.log("ERROR", message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.log("DEBUG", message, **kwargs)

    def query(
        self,
        level: str = None,
        module: str = None,
        start_time: str = None,
        end_time: str = None,
        provider: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """Query log entries"""
        entries = []

        # Read log files
        for log_file in sorted(os.listdir(self.log_dir), reverse=True):
            if not log_file.endswith(".jsonl"):
                continue

            with open(os.path.join(self.log_dir, log_file), "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())

                        # Apply filters
                        if level and entry.get("level") != level:
                            continue
                        if module and entry.get("module") != module:
                            continue
                        if start_time and entry.get("timestamp") < start_time:
                            continue
                        if end_time and entry.get("timestamp") > end_time:
                            continue
                        if provider and entry.get("provider") != provider:
                            continue

                        entries.append(entry)

                        if len(entries) >= limit:
                            return entries
                    except json.JSONDecodeError:
                        continue

        return entries

    def get_stats(self, minutes: int = 60) -> Dict:
        """Get logging statistics"""
        cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        entries = self.query(start_time=cutoff, limit=10000)

        stats = {
            "total": len(entries),
            "by_level": defaultdict(int),
            "by_module": defaultdict(int),
            "errors": []
        }

        for entry in entries:
            stats["by_level"][entry.get("level", "UNKNOWN")] += 1
            stats["by_module"][entry.get("module", "unknown")] += 1

            if entry.get("level") in ("ERROR", "CRITICAL"):
                stats["errors"].append({
                    "timestamp": entry.get("timestamp"),
                    "message": entry.get("message"),
                    "module": entry.get("module")
                })

        return {
            "total": stats["total"],
            "by_level": dict(stats["by_level"]),
            "by_module": dict(stats["by_module"]),
            "error_count": len(stats["errors"]),
            "recent_errors": stats["errors"][:5]
        }


class SLAMonitor:
    """SLA monitoring and tracking"""

    def __init__(self, data_dir: str = "data/sla"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.metrics: Dict[str, SLAMetric] = {}
        self.breach_log: List[Dict] = []
        self._load_data()

    def _load_data(self):
        """Load SLA data from disk"""
        metrics_file = os.path.join(self.data_dir, "metrics.json")
        if os.path.exists(metrics_file):
            with open(metrics_file, "r") as f:
                data = json.load(f)
                for name, mdata in data.get("metrics", {}).items():
                    self.metrics[name] = SLAMetric(**mdata)
                self.breach_log = data.get("breaches", [])

    def _save_data(self):
        """Save SLA data to disk"""
        data_file = os.path.join(self.data_dir, "metrics.json")
        with open(data_file, "w") as f:
            json.dump({
                "metrics": {name: m.__dict__ for name, m in self.metrics.items()},
                "breaches": self.breach_log[-1000:]  # Keep last 1000
            }, f, indent=2)

    def register_metric(self, name: str, target: float, window_minutes: int = 60):
        """Register an SLA metric"""
        self.metrics[name] = SLAMetric(
            name=name,
            target=target,
            window_minutes=window_minutes
        )

    def record_value(self, metric_name: str, value: float, higher_is_worse: bool = False):
        """Record a value for an SLA metric
        
        Args:
            higher_is_worse: If True, breach when value > target (e.g., latency)
                            If False, breach when value < target (e.g., availability)
        """
        if metric_name not in self.metrics:
            return

        metric = self.metrics[metric_name]
        metric.current = value

        # Check for breach
        breached = (value > metric.target) if higher_is_worse else (value < metric.target)
        if breached:
            metric.breaches += 1
            metric.last_breach = datetime.now().isoformat()

            self.breach_log.append({
                "metric": metric_name,
                "target": metric.target,
                "actual": value,
                "timestamp": datetime.now().isoformat()
            })

    def get_status(self) -> Dict:
        """Get SLA status"""
        status = {}
        for name, metric in self.metrics.items():
            status[name] = {
                "target": metric.target,
                "current": metric.current,
                "breaches": metric.breaches,
                "last_breach": metric.last_breach,
                "status": "healthy" if metric.current >= metric.target else "breach"
            }
        return status

    def get_breach_summary(self, hours: int = 24) -> Dict:
        """Get breach summary for last N hours"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        recent_breaches = [b for b in self.breach_log if b.get("timestamp", "") > cutoff]

        by_metric = defaultdict(int)
        for breach in recent_breaches:
            by_metric[breach["metric"]] += 1

        return {
            "period_hours": hours,
            "total_breaches": len(recent_breaches),
            "by_metric": dict(by_metric),
            "recent": recent_breaches[-10:]  # Last 10 breaches
        }


# Global instances
structured_logger = StructuredLogger()
sla_monitor = SLAMonitor()


# Register default SLA metrics
sla_monitor.register_metric("availability", 99.0)  # 99% availability
sla_monitor.register_metric("latency_p95", 2000.0)  # 2000ms p95 latency
sla_monitor.register_metric("error_rate", 5.0)  # <5% error rate
