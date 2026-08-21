"""Run comparable LoRA SFT and DPO experiments on one query-level split.

The script is intended for a temporary CUDA runner. It imports GPU-training
dependencies only inside ``main`` so dataset validation remains testable in the
production environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
from typing import Any


SYSTEM_PROMPT = (
    "Answer only from the supplied evidence. Every factual statement must cite "
    "an evidence ID such as [e1]. If evidence is insufficient, say so plainly."
)


def load_pairs(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pairs = payload.get("pairs", payload) if isinstance(payload, dict) else payload
    if not isinstance(pairs, list) or not pairs:
        raise ValueError(f"{path} must contain a non-empty pairs array")
    return pairs


def validate_query_split(train_pairs: list[dict[str, Any]], test_pairs: list[dict[str, Any]]) -> None:
    overlap = {row["query_id"] for row in train_pairs} & {row["query_id"] for row in test_pairs}
    if overlap:
        raise ValueError(f"Train/test query leakage: {sorted(overlap)}")


def prompt_messages(pair: dict[str, Any]) -> list[dict[str, str]]:
    evidence = "\n".join(f"[{item['evidence_id']}] {item['text']}" for item in pair["evidence"])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Evidence:\n{evidence}\n\nQuestion: {pair['query']}"},
    ]


def sft_rows(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"messages": [*prompt_messages(pair), {"role": "assistant", "content": pair["chosen"]["answer"]}]} for pair in pairs]


def dpo_rows(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "prompt": prompt_messages(pair),
            "chosen": [{"role": "assistant", "content": pair["chosen"]["answer"]}],
            "rejected": [{"role": "assistant", "content": pair["rejected"]["answer"]}],
        }
        for pair in pairs
    ]


def directory_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(str(item.relative_to(path)).encode())
        digest.update(item.read_bytes())
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=("sft", "dpo"), required=True)
    parser.add_argument("--train-split", type=Path, required=True)
    parser.add_argument("--test-split", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--beta", type=float, default=0.1)
    parser.add_argument("--wandb-project", default="strength-atlas-answer-training")
    parser.add_argument("--wandb-mode", choices=("online", "offline", "disabled"), default="offline")
    parser.add_argument("--run-name")
    parser.add_argument("--qlora", action="store_true", help="Load the base model in 4-bit NF4 for a constrained CUDA runner.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_pairs = load_pairs(args.train_split)
    test_pairs = load_pairs(args.test_split)
    validate_query_split(train_pairs, test_pairs)
    summary = {
        "method": args.method,
        "model_id": args.model_id,
        "seed": args.seed,
        "train_pairs": len(train_pairs),
        "train_queries": len({row["query_id"] for row in train_pairs}),
        "test_pairs": len(test_pairs),
        "test_queries": len({row["query_id"] for row in test_pairs}),
        "qlora": args.qlora,
    }
    if args.dry_run:
        print(json.dumps(summary, indent=2))
        return

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed
    from trl import DPOConfig, DPOTrainer, SFTConfig, SFTTrainer

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for the 3B answer-model experiment")
    set_seed(args.seed)
    random.seed(args.seed)
    os.environ["WANDB_MODE"] = args.wandb_mode
    os.environ["WANDB_PROJECT"] = args.wandb_project
    tokenizer = AutoTokenizer.from_pretrained(args.model_id)
    if args.method == "dpo":
        tokenizer.padding_side = "left"
    # Turing GPUs (for example Kaggle T4s) can report partial BF16 support but
    # fail inside attention GEMMs; only Ampere-or-newer devices use BF16 here.
    use_bf16 = torch.cuda.is_bf16_supported() and torch.cuda.get_device_capability()[0] >= 8
    quantization = None
    if args.qlora:
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16 if use_bf16 else torch.float16,
        )
        model: Any = args.model_id
    else:
        model = AutoModelForCausalLM.from_pretrained(
            args.model_id,
            torch_dtype=torch.bfloat16 if use_bf16 else torch.float16,
            device_map={"": torch.cuda.current_device()},
        )
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")
    common = dict(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        bf16=use_bf16,
        fp16=not use_bf16,
        logging_steps=1,
        eval_strategy="epoch",
        save_strategy="epoch",
        report_to="none" if args.wandb_mode == "disabled" else "wandb",
        run_name=args.run_name or f"{args.method}-seed{args.seed}",
        seed=args.seed,
    )
    if args.qlora:
        common["model_init_kwargs"] = {
            "quantization_config": quantization,
            # A quantized model must stay on the process-local training device;
            # ``auto`` may shard it across Kaggle's two T4s before Accelerate
            # prepares the trainer, which is rejected by bitsandbytes.
            "device_map": {"": torch.cuda.current_device()},
            "torch_dtype": torch.bfloat16 if use_bf16 else torch.float16,
        }
    if args.method == "sft":
        trainer = SFTTrainer(
            model=model,
            processing_class=tokenizer,
            train_dataset=Dataset.from_list(sft_rows(train_pairs)),
            eval_dataset=Dataset.from_list(sft_rows(test_pairs)),
            peft_config=lora,
            args=SFTConfig(max_length=args.max_length, **common),
        )
    else:
        trainer = DPOTrainer(
            model=model,
            ref_model=None,
            processing_class=tokenizer,
            train_dataset=Dataset.from_list(dpo_rows(train_pairs)),
            eval_dataset=Dataset.from_list(dpo_rows(test_pairs)),
            peft_config=lora,
            args=DPOConfig(max_length=args.max_length, beta=args.beta, **common),
        )
    trainer.train()
    metrics = trainer.evaluate()
    trainer.save_model(str(args.output_dir))
    summary["metrics"] = metrics
    summary["artifact_sha256"] = directory_sha256(args.output_dir)
    (args.output_dir / "training-report.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
