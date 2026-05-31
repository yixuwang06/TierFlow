"""Health monitoring and metrics."""

import os
import psutil
import threading
import time
from typing import Dict, Any

from prometheus_client import Counter, Gauge, Histogram, start_http_server

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Prometheus metrics
workflow_counter = Counter("workflow_total", "Total workflows executed")
workflow_success_counter = Counter("workflow_success_total", "Total successful workflows")
workflow_failure_counter = Counter("workflow_failure_total", "Total failed workflows")
task_duration = Histogram("task_duration_seconds", "Task execution duration")
api_request_counter = Counter("api_requests_total", "Total API requests", ["model", "status"])
memory_usage = Gauge("memory_usage_mb", "Memory usage in MB")
cpu_usage = Gauge("cpu_usage_percent", "CPU usage percentage")


class HealthMonitor:
    """Health monitoring and metrics collection."""

    def __init__(self):
        self.running = False
        self.monitor_thread = None
        self.last_heartbeat = time.time()
        self.process = psutil.Process(os.getpid())

    def start(self, port: int = 9090):
        """Start health monitoring."""
        logger.info("starting_health_monitor", port=port)

        start_http_server(port)

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        """Stop health monitoring."""
        logger.info("stopping_health_monitor")
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._collect_metrics()
                time.sleep(settings.health_check_interval)
            except Exception as e:
                logger.error("monitoring_error", error=str(e))

    def _collect_metrics(self):
        """Collect system metrics."""
        try:
            mem_info = self.process.memory_info()
            memory_mb = mem_info.rss / 1024 / 1024
            memory_usage.set(memory_mb)

            cpu_percent = self.process.cpu_percent(interval=1)
            cpu_usage.set(cpu_percent)

            if memory_mb > settings.max_memory_mb:
                logger.warning(
                    "high_memory_usage",
                    current_mb=memory_mb,
                    max_mb=settings.max_memory_mb,
                )

            self.last_heartbeat = time.time()

        except Exception as e:
            logger.error("metrics_collection_error", error=str(e))

    def heartbeat(self):
        """Update heartbeat timestamp."""
        self.last_heartbeat = time.time()

    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        time_since_heartbeat = time.time() - self.last_heartbeat

        if time_since_heartbeat > settings.heartbeat_timeout:
            logger.error("heartbeat_timeout", seconds=time_since_heartbeat)
            return False

        try:
            mem_info = self.process.memory_info()
            memory_mb = mem_info.rss / 1024 / 1024

            if memory_mb > settings.max_memory_mb * 1.5:
                logger.error("critical_memory_usage", memory_mb=memory_mb)
                return False

        except Exception as e:
            logger.error("health_check_error", error=str(e))
            return False

        return True

    def get_status(self) -> Dict[str, Any]:
        """Get current health status."""
        try:
            mem_info = self.process.memory_info()
            memory_mb = mem_info.rss / 1024 / 1024
            cpu_percent = self.process.cpu_percent(interval=0.1)

            return {
                "healthy": self.is_healthy(),
                "uptime": time.time() - self.process.create_time(),
                "memory_mb": memory_mb,
                "cpu_percent": cpu_percent,
                "last_heartbeat": self.last_heartbeat,
                "time_since_heartbeat": time.time() - self.last_heartbeat,
            }
        except Exception as e:
            logger.error("status_check_error", error=str(e))
            return {"healthy": False, "error": str(e)}
