import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Monitor(Protocol):
    def start(self) -> None: ...
    def close(self) -> None: ...
    def set_ready(self, ready: bool) -> None: ...
    def set_bot_latency(self, latency: float) -> None: ...
    def observe_event(
        self,
        event: str,
        result: str,
        duration: float,
    ) -> None: ...
    def observe_playback(
        self,
        playback_type: str,
        result: str,
    ) -> None: ...


class DisabledMonitor:
    """
    Empty class that follows the Monitor protocol to avoid enabled-state checks
    throughout the codebase.
    """

    def start(self) -> None: ...
    def close(self) -> None: ...
    def set_ready(self, ready: bool) -> None: ...
    def set_bot_latency(self, latency: float) -> None: ...
    def observe_event(
        self,
        event: str,
        result: str,
        duration: float,
    ) -> None: ...
    def observe_playback(
        self,
        playback_type: str,
        result: str,
    ) -> None: ...


def init_monitor(*, enabled: bool) -> Monitor:
    if not enabled:
        logger.debug(
            "Prometheus metrics are disabled",
            extra={"event": "prometheus_metrics_disabled"},
        )
        return DisabledMonitor()

    try:
        from hatsune_miku_bot.monitoring.prometheus import (
            PrometheusMonitoring,
        )
    except ModuleNotFoundError as err:
        if err.name != "prometheus_client":
            raise
        raise RuntimeError(
            "Prometheus monitoring is enabled but not installed.\n"
            "Run: uv sync --extra prometheus"
        ) from err

    logger.info("Starting prometheus http server")
    return PrometheusMonitoring()
