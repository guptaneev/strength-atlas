# Answer training experiment v1

Kaggle run: `https://www.kaggle.com/code/guptaneev/strength-atlas-sft-vs-dpo`

## Setup

- Base model: `Qwen/Qwen2.5-3B-Instruct`
- Training data: 74 human preference pairs across 19 queries
- Held-out data: 17 human preference pairs across 5 query-disjoint queries
- Method: LoRA, two epochs, batch size 1, gradient accumulation 8
- Context length: 256 tokens
- Hardware: one T4 made visible to each training process
- Runs: SFT seed 42; DPO seeds 42, 43, and 44
- Tracking: W&B offline logs in the Kaggle output archive

QLoRA was attempted first, but the Kaggle T4/bitsandbytes combination failed in
CUDA matrix multiplication. Full FP16 LoRA was used instead. The shorter context
was required to fit the 3B model on a 14.6 GiB T4 without data-parallel duplication.

## Results

- All four runs completed and produced checksummed adapters.
- DPO held-out losses were 0.6363, 0.6547, and 0.6649. These are seed-stability
  indicators within DPO and must not be compared directly with the SFT loss,
  because the objectives differ.
- On five generated held-out answers, DPO cited supplied evidence on 100% of
  answers versus 60% for the base and SFT outputs.
- DPO's mean overlap with non-empty gold citation sets was 0.375 versus 0.25 for
  the base and SFT outputs.
- DPO answers averaged 23.8 words across seeds versus 32.4 for the base, so the
  observed citation improvement is not explained by greater verbosity.
- Every generated citation referred to an ID present in the supplied evidence.
- SFT produced the same deterministic answer as the base model on all five
  queries; this run did not demonstrate a generation-level improvement.

## What this does not prove

The automatic checks are not a substitute for blind human preference review.
The local generated file contains 25 answers (five models by five queries)
ready for that review. The uncommitted `blind-human-review-packet.json` hides
model identities and includes the supplied evidence; its separate decoding key
is generated under `var/atlas/`. Raw answer and preference records are excluded
from the public repository. Five queries are also too few for a strong general
conclusion.
Do not claim that DPO improved answer quality until those answers are judged
blindly and the human preference result is reported separately.

The full adapter archive and raw generated answers are retained in the Kaggle
version output. This public folder keeps only the small training reports and
mechanical evaluation summary needed to audit the experiment without committing
model binaries or raw evaluation records.
