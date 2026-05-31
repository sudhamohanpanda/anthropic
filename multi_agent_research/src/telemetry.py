"""OpenTelemetry-backed token telemetry with a lightweight local dashboard."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

logger = logging.getLogger("research_system")

try:
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        MetricExportResult,
        MetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import Resource
except ImportError:  # pragma: no cover - graceful fallback when optional deps are absent.
    metrics = None
    MeterProvider = None
    Resource = None
    ConsoleMetricExporter = None
    PeriodicExportingMetricReader = None
    MetricExporter = object
    MetricExportResult = None


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Research Token Telemetry</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
    header { padding: 1rem 1.5rem; border-bottom: 1px solid #1e293b; }
    main { display: grid; gap: 1rem; padding: 1rem 1.5rem 2rem; }
    .card { background: #111827; border: 1px solid #1f2937; border-radius: 14px; padding: 1rem; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
    .stat-value { font-size: 1.8rem; font-weight: 700; margin-top: 0.35rem; }
    canvas { width: 100%; height: 340px; background: #020617; border-radius: 12px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 0.65rem; border-bottom: 1px solid #1f2937; }
    .muted { color: #94a3b8; font-size: 0.9rem; }
    a { color: #38bdf8; }
  </style>
</head>
<body>
  <header>
    <h1 style=\"margin:0;\">Research Token Telemetry Dashboard</h1>
    <p class=\"muted\" style=\"margin:0.35rem 0 0;\">Live OpenTelemetry metrics exported from the coordinator token guard.</p>
  </header>
  <main>
    <section class=\"stats\">
      <div class=\"card\"><div>Total input tokens</div><div class=\"stat-value\" id=\"inputTotal\">0</div></div>
      <div class=\"card\"><div>Total saved tokens</div><div class=\"stat-value\" id=\"savedTotal\">0</div></div>
      <div class=\"card\"><div>Estimated spend (USD)</div><div class=\"stat-value\" id=\"costTotal\">0.000000</div></div>
      <div class=\"card\"><div>Series tracked</div><div class=\"stat-value\" id=\"seriesCount\">0</div></div>
    </section>

    <section class=\"card\">
      <h2 style=\"margin-top:0;\">Live metrics</h2>
      <canvas id=\"chart\" width=\"1200\" height=\"340\"></canvas>
      <p class=\"muted\">Polling every second from <code>/api/metrics</code>.</p>
    </section>

    <section class=\"card\">
      <h2 style=\"margin-top:0;\">Latest exported values</h2>
      <table>
        <thead><tr><th>Metric</th><th>Latest</th><th>Samples</th></tr></thead>
        <tbody id=\"metricRows\"></tbody>
      </table>
    </section>
  </main>
  <script>
    const colors = ["#38bdf8", "#22c55e", "#f97316", "#e879f9", "#facc15", "#fb7185"];
    const canvas = document.getElementById("chart");
    const ctx = canvas.getContext("2d");

    function drawChart(seriesEntries) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#020617";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const padding = 50;
      const width = canvas.width - padding * 2;
      const height = canvas.height - padding * 2;
      const points = seriesEntries.flatMap(([, points]) => points);

      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 5; i += 1) {
        const y = padding + (height / 5) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(canvas.width - padding, y);
        ctx.stroke();
      }

      if (!points.length) {
        ctx.fillStyle = "#94a3b8";
        ctx.font = "18px sans-serif";
        ctx.fillText("Waiting for metrics...", padding, padding + 20);
        return;
      }

      const minTime = Math.min(...points.map((point) => point.timestamp));
      const maxTime = Math.max(...points.map((point) => point.timestamp));
      const maxValue = Math.max(...points.map((point) => point.value), 1);
      const timeRange = Math.max(maxTime - minTime, 1);

      seriesEntries.forEach(([label, samples], index) => {
        ctx.strokeStyle = colors[index % colors.length];
        ctx.lineWidth = 2;
        ctx.beginPath();
        samples.forEach((point, sampleIndex) => {
          const x = padding + ((point.timestamp - minTime) / timeRange) * width;
          const y = padding + height - (point.value / maxValue) * height;
          if (sampleIndex === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        });
        ctx.stroke();
        ctx.fillStyle = colors[index % colors.length];
        ctx.font = "14px sans-serif";
        ctx.fillText(label, padding + 10, padding + 18 + index * 18);
      });
    }

    function renderRows(seriesEntries) {
      const rows = document.getElementById("metricRows");
      rows.innerHTML = "";
      seriesEntries.forEach(([label, samples]) => {
        const latest = samples[samples.length - 1];
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${label}</td><td>${latest ? latest.value.toFixed(6) : "0"}</td><td>${samples.length}</td>`;
        rows.appendChild(tr);
      });
    }

    function updateTotals(snapshot) {
      const totals = snapshot.totals || {};
      document.getElementById("inputTotal").textContent = Math.round(totals["research.tokens.input"] || 0).toString();
      document.getElementById("savedTotal").textContent = Math.round(totals["research.tokens.saved"] || 0).toString();
      document.getElementById("costTotal").textContent = (totals["research.token_cost.usd"] || 0).toFixed(6);
      document.getElementById("seriesCount").textContent = Object.keys(snapshot.series || {}).length.toString();
    }

    async function poll() {
      const response = await fetch("/api/metrics", { cache: "no-store" });
      const snapshot = await response.json();
      const seriesEntries = Object.entries(snapshot.series || {});
      updateTotals(snapshot);
      renderRows(seriesEntries);
      drawChart(seriesEntries);
    }

    poll();
    setInterval(poll, 1000);
  </script>
</body>
</html>
"""


@dataclass(slots=True)
class LiveMetricStore:
    max_points: int = 180
    _series: dict[str, deque[dict[str, float]]] = field(init=False, repr=False)
    _totals: dict[str, float] = field(init=False, repr=False)
    _lock: threading.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._series: dict[str, deque[dict[str, float]]] = defaultdict(lambda: deque(maxlen=self.max_points))
        self._totals: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    def add_point(self, metric_name: str, value: float, attributes: dict[str, Any] | None) -> None:
        timestamp = time.time()
        series_name = _series_name(metric_name, attributes)
        with self._lock:
            self._series[series_name].append({"timestamp": timestamp, "value": float(value)})
            self._totals[metric_name] += float(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "series": {name: list(points) for name, points in self._series.items()},
                "totals": dict(self._totals),
                "updated_at": time.time(),
            }


class LiveMetricExporter(MetricExporter):
    """OpenTelemetry metric exporter that pushes aggregate points into a local dashboard store."""

    def __init__(self, store: LiveMetricStore):
        super().__init__()
        self._store = store

    def export(self, metrics_data: Any, timeout_millis: float = 10_000, **_: Any) -> Any:
        for resource_metric in getattr(metrics_data, "resource_metrics", []):
            for scope_metric in getattr(resource_metric, "scope_metrics", []):
                for metric in getattr(scope_metric, "metrics", []):
                    for point in getattr(getattr(metric, "data", None), "data_points", []):
                        value = _extract_numeric_value(point)
                        if value is None:
                            continue
                        self._store.add_point(metric.name, value, dict(getattr(point, "attributes", {}) or {}))
        return MetricExportResult.SUCCESS if MetricExportResult else None

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        return True

    def shutdown(self, timeout_millis: float = 30_000, **_: Any) -> None:
        return None


class _DashboardRequestHandler(BaseHTTPRequestHandler):
    store: LiveMetricStore

    def do_GET(self) -> None:  # noqa: N802 - inherited method name
        if self.path in {"/", "/index.html"}:
            self._write_response(200, _DASHBOARD_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/api/metrics":
            payload = json.dumps(self.store.snapshot()).encode("utf-8")
            self._write_response(200, payload, "application/json; charset=utf-8")
            return
        self._write_response(404, b"Not Found", "text/plain; charset=utf-8")

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("Telemetry dashboard: " + format, *args)

    def _write_response(self, status_code: int, body: bytes, content_type: str) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@dataclass(slots=True)
class TokenTelemetry:
    meter: Any
    input_tokens_counter: Any
    saved_tokens_counter: Any
    estimated_cost_counter: Any
    store: LiveMetricStore | None = None
    meter_provider: Any = None
    dashboard_url: str | None = None
    server: ThreadingHTTPServer | None = None
    server_thread: threading.Thread | None = None

    def record_input_tokens(self, token_count: int, attributes: dict[str, Any] | None = None) -> None:
        if token_count <= 0:
            return
        self.input_tokens_counter.add(int(token_count), attributes=attributes or {})

    def record_saved_tokens(self, token_count: int, attributes: dict[str, Any] | None = None) -> None:
        if token_count <= 0:
            return
        self.saved_tokens_counter.add(int(token_count), attributes=attributes or {})

    def record_estimated_cost(
        self,
        input_tokens: int,
        output_tokens: int = 0,
        model: str = "claude-3-5-sonnet-latest",
        attributes: dict[str, Any] | None = None,
    ) -> float:
        if input_tokens <= 0 and output_tokens <= 0:
            return 0.0

        input_cost_per_million = float(os.getenv("RESEARCH_INPUT_COST_PER_MILLION", "3.0"))
        output_cost_per_million = float(os.getenv("RESEARCH_OUTPUT_COST_PER_MILLION", "15.0"))
        estimated_cost = ((input_tokens * input_cost_per_million) + (output_tokens * output_cost_per_million)) / 1_000_000

        metric_attributes = {"model": model}
        if attributes:
            metric_attributes.update(attributes)
        self.estimated_cost_counter.add(estimated_cost, attributes=metric_attributes)
        return estimated_cost

    def force_flush(self) -> None:
        if self.meter_provider is not None:
            self.meter_provider.force_flush()

    def shutdown(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.meter_provider is not None:
            self.meter_provider.shutdown()


class NoOpTokenTelemetry(TokenTelemetry):
    def __init__(self) -> None:
        super().__init__(meter=None, input_tokens_counter=None, saved_tokens_counter=None, estimated_cost_counter=None)

    def record_input_tokens(self, token_count: int, attributes: dict[str, Any] | None = None) -> None:
        return None

    def record_saved_tokens(self, token_count: int, attributes: dict[str, Any] | None = None) -> None:
        return None

    def record_estimated_cost(
        self,
        input_tokens: int,
        output_tokens: int = 0,
        model: str = "claude-3-5-sonnet-latest",
        attributes: dict[str, Any] | None = None,
    ) -> float:
        return 0.0

    def force_flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


_TELEMETRY_SINGLETON: TokenTelemetry | None = None


def configure_token_telemetry(
    service_name: str = "multi-agent-research",
    dashboard_host: str = "127.0.0.1",
    dashboard_port: int = 8765,
    export_interval_millis: int = 1_000,
    enable_console_exporter: bool = False,
    start_dashboard: bool = True,
) -> TokenTelemetry:
    """Configure OpenTelemetry counters and optionally expose a local live dashboard."""
    global _TELEMETRY_SINGLETON

    if _TELEMETRY_SINGLETON is not None:
        return _TELEMETRY_SINGLETON

    if metrics is None or MeterProvider is None or Resource is None or PeriodicExportingMetricReader is None:
        logger.warning("OpenTelemetry packages are unavailable. Falling back to no-op telemetry.")
        _TELEMETRY_SINGLETON = NoOpTokenTelemetry()
        return _TELEMETRY_SINGLETON

    store = LiveMetricStore()
    exporters: list[Any] = [LiveMetricExporter(store)]
    if enable_console_exporter and ConsoleMetricExporter is not None:
        exporters.append(ConsoleMetricExporter())

    readers = [
        PeriodicExportingMetricReader(exporter, export_interval_millis=export_interval_millis)
        for exporter in exporters
    ]
    meter_provider = MeterProvider(resource=Resource.create({"service.name": service_name}), metric_readers=readers)
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter(service_name)

    telemetry = TokenTelemetry(
        meter=meter,
        input_tokens_counter=meter.create_counter(
            name="research.tokens.input",
            unit="1",
            description="Incoming token volume reaching the synthesizer handoff.",
        ),
        saved_tokens_counter=meter.create_counter(
            name="research.tokens.saved",
            unit="1",
            description="Tokens removed by compress_payload before synthesis.",
        ),
        estimated_cost_counter=meter.create_counter(
            name="research.token_cost.usd",
            unit="USD",
            description="Estimated token spend derived from current input and output token counts.",
        ),
        store=store,
        meter_provider=meter_provider,
    )

    if start_dashboard:
        telemetry.server, telemetry.server_thread = _start_dashboard_server(store, dashboard_host, dashboard_port)
        telemetry.dashboard_url = f"http://{dashboard_host}:{dashboard_port}"
        logger.info("Token telemetry dashboard available at %s", telemetry.dashboard_url)

    _TELEMETRY_SINGLETON = telemetry
    return telemetry


def get_token_telemetry() -> TokenTelemetry:
    if _TELEMETRY_SINGLETON is None:
        return configure_token_telemetry(start_dashboard=False)
    return _TELEMETRY_SINGLETON


def _start_dashboard_server(
    store: LiveMetricStore,
    host: str,
    port: int,
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    handler_class = type(
        "TokenTelemetryDashboardHandler",
        (_DashboardRequestHandler,),
        {"store": store},
    )
    server = ThreadingHTTPServer((host, port), handler_class)
    thread = threading.Thread(target=server.serve_forever, name="token-telemetry-dashboard", daemon=True)
    thread.start()
    return server, thread


def _series_name(metric_name: str, attributes: dict[str, Any] | None) -> str:
    if not attributes:
        return metric_name
    suffix = ", ".join(f"{key}={value}" for key, value in sorted(attributes.items()))
    return f"{metric_name} [{suffix}]"


def _extract_numeric_value(point: Any) -> float | None:
    if hasattr(point, "value"):
        return float(point.value)
    if hasattr(point, "sum"):
        return float(point.sum)
    return None

