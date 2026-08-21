"""Generate held-out answers for base and adapter models.

This script is intentionally notebook-independent. Upload the fixed test split
and run it on a temporary GPU; the output is directly consumable by
``atlas ml answer-evaluate``.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def load_test_queries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pairs = payload.get("pairs", payload) if isinstance(payload, dict) else payload
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Test split must contain a non-empty pairs array")
    by_query: dict[str, dict[str, Any]] = {}
    for pair in pairs:
        query_id = pair["query_id"]
        if query_id not in by_query:
            by_query[query_id] = pair
    return list(by_query.values())


def build_prompt(pair: dict[str, Any], tokenizer: Any) -> str:
    evidence = "\n".join(
        f"[{item['evidence_id']}] {item['text']}" for item in pair.get("evidence", [])
    )
    messages = [
        {
            "role": "system",
            "content": (
                "Answer only from the supplied evidence. Every factual statement "
                "must cite an evidence ID such as [e1]. If evidence is insufficient, "
                "say so plainly."
            ),
        },
        {"role": "user", "content": f"Evidence:\n{evidence}\n\nQuestion: {pair['query']}"},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def generate(model: Any, tokenizer: Any, pair: dict[str, Any], max_new_tokens: int) -> str:
    import torch

    prompt = build_prompt(pair, tokenizer)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(
        output[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-split", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--adapter", action="append", default=[], help="name=path")
    parser.add_argument("--max-new-tokens", type=int, default=180)
    args = parser.parse_args()

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
    except ImportError as exc:
        raise SystemExit(
            "GPU dependencies are missing or incompatible. Run this first in a fresh "
            "Kaggle cell: !pip install -q -U 'transformers>=4.51,<5' 'peft>=0.15,<1' "
            "'accelerate>=1.4,<2' 'huggingface-hub>=0.34,<1'"
        ) from exc

    pairs = load_test_queries(args.test_split)
    random.seed(42)
    tokenizer = AutoTokenizer.from_pretrained(args.model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.model_id, torch_dtype=torch.float16, device_map="auto"
    )
    base.eval()
    models: list[tuple[str, Any]] = [("base", base)]
    adapter_names: dict[str, Any] = {}
    for spec in args.adapter:
        if "=" not in spec:
            raise ValueError(f"Adapter must use name=path: {spec}")
        name, path = spec.split("=", 1)
        if not adapter_names:
            adapter_model = PeftModel.from_pretrained(base, path, adapter_name=name)
        else:
            adapter_model.load_adapter(path, adapter_name=name)
        adapter_names[name] = adapter_model
        models.append((name, adapter_model))

    records: list[dict[str, Any]] = []
    for model_name, model in models:
        if model_name in adapter_names:
            model.set_adapter(model_name)
        for pair in pairs:
            answer = generate(model, tokenizer, pair, args.max_new_tokens)
            chosen = pair.get("chosen", {})
            records.append(
                {
                    "model": model_name,
                    "query_id": pair["query_id"],
                    "answer": answer,
                    "evidence_ids": [x["evidence_id"] for x in pair.get("evidence", [])],
                    "gold_citations": chosen.get("cited_evidence_ids", []),
                    "reference_answer": chosen.get("answer"),
                    "label_source": pair.get("label_source", payload_label_source(args.test_split)),
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} records to {args.output}")


def payload_label_source(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("label_source", "human")) if isinstance(payload, dict) else "unknown"


if __name__ == "__main__":
    main()
