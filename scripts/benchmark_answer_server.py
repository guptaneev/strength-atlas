"""Benchmark a deployed answer-model HTTP endpoint."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any
from urllib.request import Request, urlopen


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def benchmark(
    *,
    url: str,
    payload: dict[str, Any],
    api_key: str | None,
    warmups: int,
    iterations: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = json.dumps(payload).encode("utf-8")
    latencies: list[float] = []
    successes = 0
    for index in range(warmups + iterations):
        started = time.perf_counter()
        with urlopen(Request(url, data=body, headers=headers, method="POST"), timeout=timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
        elapsed_ms = (time.perf_counter() - started) * 1000
        if index >= warmups:
            latencies.append(elapsed_ms)
            successes += int(bool(result.get("answer")))
    total_seconds = sum(latencies) / 1000
    return {
        "url": url,
        "warmups": warmups,
        "iterations": iterations,
        "p50_ms": statistics.median(latencies),
        "p99_ms": percentile(latencies, 0.99),
        "mean_ms": statistics.fmean(latencies),
        "requests_per_second": iterations / total_seconds if total_seconds else None,
        "success_rate": successes / iterations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api-key")
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    args = parser.parse_args()
    report = benchmark(
        url=args.url,
        payload=json.loads(args.payload.read_text(encoding="utf-8")),
        api_key=args.api_key,
        warmups=args.warmups,
        iterations=args.iterations,
        timeout_seconds=args.timeout_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
