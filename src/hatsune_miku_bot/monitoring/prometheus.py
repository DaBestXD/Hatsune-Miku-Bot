from __future__ import annotations

import logging

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)

logger = logging.getLogger(__name__)


class PrometheusMonitoring:
    def __init__(
        self,
        *,
        addr: str = "127.0.0.1",
        port: int = 8000,
        registry: CollectorRegistry | None = None,
    ) -> None:
        self.addr = addr
        self.port = port
        self.registry = (
            registry if registry is not None else CollectorRegistry()
        )
        self._init_collectors()

    def _init_collectors(self) -> None:
        self.ready_status = Gauge(
            name="ready",
            documentation="Whether the bot is ready",
            namespace="hatsune_miku_bot",
            registry=self.registry,
        )
        self.bot_latency = Gauge(
            name="discord_gateway_latency_seconds",
            documentation=(
                "Discord Gateway heartbeat round-trip latency in seconds"
            ),
            namespace="hatsune_miku_bot",
            registry=self.registry,
        )
        self.bot_latency_distribution = Histogram(
            name="discord_gateway_latency_samples_seconds",
            documentation=(
                "Distribution of sampled Discord Gateway heartbeat "
                "round-trip latency"
            ),
            buckets=(
                0.025,
                0.05,
                0.075,
                0.1,
                0.15,
                0.25,
                0.5,
                1.0,
                2.5,
            ),
            namespace="hatsune_miku_bot",
            registry=self.registry,
        )
        self.events_total = Counter(
            name="events_total",
            documentation="Total number of guild controller events processed",
            labelnames=("event", "result"),
            namespace="hatsune_miku_bot",
            registry=self.registry,
        )
        self.event_duration = Histogram(
            name="event_duration_seconds",
            documentation="Guild controller event processing duration",
            labelnames=("event",),
            buckets=(
                0.0001,
                0.00025,
                0.0005,
                0.001,
                0.0025,
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                0.75,
                1.0,
                1.5,
                2.0,
                2.5,
                3.0,
                3.5,
                4.0,
                4.5,
                5.0,
                7.5,
                10.0,
            ),
            namespace="hatsune_miku_bot",
            registry=self.registry,
        )
        self.playback_events_total = Counter(
            name="playback_events_total",
            documentation="Total number of playback lifecycle events",
            labelnames=("playback_type", "result"),
            namespace="hatsune_miku_bot",
            registry=self.registry,
        )

    def start(self) -> None:
        self.server, self.thread = start_http_server(
            port=self.port,
            addr=self.addr,
            registry=self.registry,
        )

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def set_ready(self, ready: bool) -> None:
        self.ready_status.set(int(ready))

    def set_bot_latency(self, latency: float) -> None:
        self.bot_latency.set(latency)
        self.bot_latency_distribution.observe(latency)

    def observe_event(
        self,
        event: str,
        result: str,
        duration: float,
    ) -> None:
        self.events_total.labels(
            event=event,
            result=result,
        ).inc()

        self.event_duration.labels(
            event=event,
        ).observe(duration)

    def observe_playback(
        self,
        playback_type: str,
        result: str,
    ) -> None:
        self.playback_events_total.labels(
            playback_type=playback_type,
            result=result,
        ).inc()
