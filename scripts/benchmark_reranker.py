"""Benchmark 50-candidate reranking and CPU int8 dynamic quantization."""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import time
from collections import defaultdict
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from atlas.ml.dataset import load_dataset
from atlas.ml.training import TrainingPair, _all_pairs
from atlas.search.metrics import evaluate_ranking


class CrossEncoder:
    def __init__(self, model_path: str, *, device: str, int8: bool) -> None:
        if int8 and device != "cpu":
            raise ValueError("int8 dynamic quantization is supported only for CPU benchmarks")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSequenceClassification.from_pretrained(model_path)
        if int8:
            supported_engines = torch.backends.quantized.supported_engines
            if not supported_engines:
                raise RuntimeError("No PyTorch quantized CPU backend is available.")
            torch.backends.quantized.engine = supported_engines[0]
            model = torch.ao.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
        self.model = model.to(device).eval()
        self.device = device

    def score(self, query: str, texts: list[str], *, batch_size: int) -> list[float]:
        values: list[float] = []
        with torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                encoded = self.tokenizer(
                    [query] * len(batch),
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=256,
                    return_tensors="pt",
                ).to(self.device)
                values.extend(float(value) for value in self.model(**encoded).logits.squeeze(-1).detach().cpu().tolist())
        return values


def percentile_ms(samples: list[float], percentile: float) -> float:
    if not samples:
        raise ValueError("samples must not be empty")
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * percentile) - 1))]


def benchmark_latency(scorer: CrossEncoder, query: str, texts: list[str], *, batch_size: int, warmups: int, iterations: int) -> dict[str, float | int]:
    for _ in range(warmups):
        scorer.score(query, texts, batch_size=batch_size)
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        scorer.score(query, texts, batch_size=batch_size)
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "candidate_count": len(texts),
        "samples": iterations,
        "p50_ms": percentile_ms(samples, 0.50),
        "p99_ms": percentile_ms(samples, 0.99),
        "throughput_candidates_per_second": len(texts) * 1000 / sum(samples) * len(samples),
    }


def evaluate_quality(scorer: CrossEncoder, pairs: list[TrainingPair], *, batch_size: int) -> dict[str, float | int]:
    grouped: dict[str, list[TrainingPair]] = defaultdict(list)
    for pair in pairs:
        grouped[pair.query_id].append(pair)
    baseline_ndcg: list[float] = []
    reranker_ndcg: list[float] = []
    baseline_recall_at_3: list[float] = []
    reranker_recall_at_3: list[float] = []
    for query_pairs in grouped.values():
        model_scores = scorer.score(query_pairs[0].query, [pair.candidate_text for pair in query_pairs], batch_size=batch_size)
        ranked = [pair for _, pair in sorted(zip(model_scores, query_pairs, strict=True), key=lambda row: row[0], reverse=True)]
        baseline = sorted(query_pairs, key=lambda pair: pair.baseline_rank if pair.baseline_rank is not None else 10**9)
        total_relevant = sum(pair.relevance > 0 for pair in query_pairs)
        baseline_ndcg.append(evaluate_ranking([pair.relevance for pair in baseline], total_relevant=total_relevant, k=10).ndcg)
        reranker_ndcg.append(evaluate_ranking([pair.relevance for pair in ranked], total_relevant=total_relevant, k=10).ndcg)
        baseline_recall_at_3.append(evaluate_ranking([pair.relevance for pair in baseline], total_relevant=total_relevant, k=3).recall)
        reranker_recall_at_3.append(evaluate_ranking([pair.relevance for pair in ranked], total_relevant=total_relevant, k=3).recall)
    return {
        "queries": len(grouped),
        "baseline_ndcg_at_10": statistics.fmean(baseline_ndcg) if baseline_ndcg else 0.0,
        "reranker_ndcg_at_10": statistics.fmean(reranker_ndcg) if reranker_ndcg else 0.0,
        "baseline_recall_at_3": statistics.fmean(baseline_recall_at_3) if baseline_recall_at_3 else 0.0,
        "reranker_recall_at_3": statistics.fmean(reranker_recall_at_3) if reranker_recall_at_3 else 0.0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--program-dataset", required=True)
    parser.add_argument("--program-review", required=True)
    parser.add_argument("--evidence-dataset", required=True)
    parser.add_argument("--evidence-review", required=True)
    parser.add_argument("--fixed-evaluation-splits", required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--skip-int8", action="store_true", help="Run only the FP32 latency and quality measurement.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable on this machine; run the same command on a CUDA runner.")
    pairs = _all_pairs(
        [
            (load_dataset(args.program_dataset, require_complete_judgments=True), json.loads(Path(args.program_review).read_text(encoding="utf-8"))),
            (load_dataset(args.evidence_dataset, require_complete_judgments=True), json.loads(Path(args.evidence_review).read_text(encoding="utf-8"))),
        ]
    )
    fixed_splits = json.loads(Path(args.fixed_evaluation_splits).read_text(encoding="utf-8"))
    test_ids = set(fixed_splits["test"])
    test_pairs = [pair for pair in pairs if pair.query_id in test_ids]
    candidate_texts = list(dict.fromkeys(pair.candidate_text for pair in pairs))
    if not candidate_texts:
        raise SystemExit("No candidate text is available for benchmarking")
    benchmark_texts = (candidate_texts * math.ceil(50 / len(candidate_texts)))[:50]
    query = test_pairs[0].query
    fp32 = CrossEncoder(args.model_path, device=args.device, int8=False)
    fp32_result = {
        "latency": benchmark_latency(fp32, query, benchmark_texts, batch_size=args.batch_size, warmups=args.warmups, iterations=args.iterations),
        "quality": evaluate_quality(fp32, test_pairs, batch_size=args.batch_size),
    }
    result: dict[str, object] = {
        "device": args.device,
        "model_path": str(args.model_path),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "torch_version": torch.__version__,
        "batch_size": args.batch_size,
        "warmups": args.warmups,
        "iterations": args.iterations,
        "fp32": fp32_result,
    }
    if args.device == "cpu" and not args.skip_int8:
        if not torch.backends.quantized.supported_engines:
            result["int8"] = {"status": "unavailable", "reason": "No PyTorch quantized CPU backend is available."}
            _emit_report(result, args.output)
            return 0
        try:
            int8 = CrossEncoder(args.model_path, device="cpu", int8=True)
        except RuntimeError as exc:
            result["int8"] = {"status": "unavailable", "reason": str(exc)}
            _emit_report(result, args.output)
            return 0
        int8_result = {
            "latency": benchmark_latency(int8, query, benchmark_texts, batch_size=args.batch_size, warmups=args.warmups, iterations=args.iterations),
            "quality": evaluate_quality(int8, test_pairs, batch_size=args.batch_size),
        }
        result["int8"] = int8_result
        result["int8_p50_speedup_percent"] = (
            (fp32_result["latency"]["p50_ms"] / int8_result["latency"]["p50_ms"] - 1) * 100
        )
        result["int8_quality_delta_ndcg_at_10"] = int8_result["quality"]["reranker_ndcg_at_10"] - fp32_result["quality"]["reranker_ndcg_at_10"]
    _emit_report(result, args.output)
    return 0


def _emit_report(result: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(result, indent=2) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    raise SystemExit(main())
