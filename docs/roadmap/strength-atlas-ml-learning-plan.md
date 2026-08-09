# Strength Atlas ML Learning Plan

This is the learner-first companion to the [Strength Atlas ML Development Plan](strength-atlas-ml-development-plan.md).

It turns the larger roadmap into a sequence of manageable learning projects. The aim is not to move quickly through a list of libraries. The aim is to understand enough of each idea to make a good decision, implement it in Strength Atlas, measure the result, and explain what happened.

## The destination

Strength Atlas currently retrieves programs with embeddings and similarity search. The learning project will investigate whether a learned cross-encoder reranker improves the relevance of those results:

```text
query
  ↓
embedding retrieval: top 20–50 candidates
  ↓
cross-encoder reranking
  ↓
top 10 programs in the API response
```

The main question is:

> Does the reranker improve held-out nDCG@10 without making the search experience unacceptably slow?

The final answer may be “not yet” or “no.” A carefully measured negative result is still a successful learning outcome.

## How to use this plan

Work in short cycles. Each cycle should produce four things:

1. A concept you can explain in plain language.
2. A small implementation you wrote or substantially understood.
3. A measurement, plot, or comparison.
4. A short note about what surprised you and what you will do next.

Do not advance because the code runs. Advance when you can answer “why?” about the important parts of the code and results.

## The AI-assisted learning rule

Use AI as a tutor, reviewer, debugging partner, and research assistant. Keep the important reasoning yours.

Before asking AI to write code, write down:

- what problem you are solving;
- what you think the inputs and outputs should be;
- what you expect to happen;
- what you do not understand yet.

When AI provides code:

- ask it to explain the tensor shapes and data flow;
- implement a small version yourself before accepting a large abstraction;
- run the code and inspect its output;
- change one detail and predict the effect before rerunning it;
- ask for tests, failure cases, and a simpler alternative;
- do not keep code you cannot explain.

Useful prompts:

```text
Act as a tutor. Do not give me the final implementation yet.
Ask me questions that reveal whether I understand this concept.
```

```text
Review this training loop for correctness. First identify questions
I should answer myself, then give hints, then show the fix only if needed.
```

```text
Here are my tensor shapes, metrics, and observations. Help me form
three hypotheses for what happened. Do not choose the hypothesis for me.
```

```text
Quiz me on this code as if I were explaining it in an ML interview.
Focus on tradeoffs and failure modes, not library trivia.
```

Keep an `experiments/learning-notes/` journal or equivalent notes file. Record AI-assisted work when it materially affects an implementation or interpretation: the question asked, the answer used, and how you verified it.

## A gentle progression

### Stage 0 — Orient yourself in the existing system

Learn enough of the current repository to trace one search request from the API or CLI to its result.

Study:

- the product requirements;
- the active MVP technical plan;
- `src/atlas/search/`;
- the existing search evaluation fixture and tests;
- the database fields used to represent programs and sources.

Build:

- a one-page diagram of the current search flow;
- a short explanation of where embeddings are created, stored, compared, and returned;
- one reproducible command or script that runs the existing baseline evaluation.

Ask AI to quiz you on the code path after you have read it. Ask it to point out likely assumptions, but verify those assumptions in the repository.

Exit check:

> Can I explain the current search system and identify the exact boundary where a reranker could be inserted?

### Stage 1 — Learn PyTorch by building a tiny model

Do not begin with a transformer. Build a small classifier using `nn.Module`, a `Dataset`, a `DataLoader`, a loss function, and an optimizer.

Understand:

- tensors and dimensions;
- forward pass and logits;
- loss and gradients;
- `zero_grad()`, `backward()`, and `step()`;
- `train()`, `eval()`, and `no_grad()`;
- validation, checkpoints, and reproducible seeds.

Build:

- a tiny synthetic classification problem;
- a training loop written by you;
- training and validation curves;
- one deliberate overfitting example and one underfitting example;
- CPU execution and optional GPU detection.

AI should help you inspect errors and quiz your understanding. Ask it to annotate shapes line by line, then remove the annotations and reproduce the explanation yourself.

Exit check:

> Can I predict what changes when I alter the learning rate, batch size, model capacity, or number of epochs?

### Stage 2 — Learn retrieval evaluation before training a model

The model is not the goal; improved retrieval is. Learn how to measure retrieval before building a reranker.

Understand:

- queries, documents, candidates, and relevance judgments;
- why relevance can be graded rather than binary;
- nDCG@10, MRR, Recall@10, and Precision@10;
- why query-level train/validation/test splits matter;
- leakage and why a random row split can be misleading.

Build:

- a small labeled set of realistic Strength Atlas queries;
- explicit relevance grades and written labeling guidance;
- deterministic metric calculations with hand-worked examples;
- a frozen test set that you will not tune against.

Use AI to propose ambiguous queries and edge cases, not to decide relevance without your review. Human judgment and documented labeling rules are part of the dataset.

Exit check:

> Can I calculate one metric by hand and explain which kinds of ranking errors it rewards or penalizes?

### Stage 3 — Establish and understand the baseline

Run the existing embedding retrieval system against the dataset. This is the control group for every later experiment.

Build:

- a baseline evaluation command;
- saved predictions and metric results;
- a small error-analysis table;
- examples of strong results, obvious misses, and ambiguous cases.

For each error, classify the likely cause: vocabulary mismatch, missing constraint, poor metadata, bad source content, candidate-pool failure, or ranking failure.

Ask AI to cluster your error descriptions and suggest hypotheses. Do not let it turn hypotheses into conclusions until you test them.

Exit check:

> Can I tell whether a future reranker is failing because the right document was never retrieved or because it was ranked too low?

### Stage 4 — Build the simplest useful reranker

Learn the difference between a bi-encoder and a cross-encoder. A cross-encoder reads the query and candidate together, which can improve ranking but costs more inference time.

Start small:

- choose a modest pretrained transformer;
- tokenize `(query, candidate)` pairs;
- produce one relevance score;
- train on positive examples and easy/hard negatives;
- rerank only the baseline candidate pool.

First implement a thin, readable training and inference path. Avoid building a general framework.

AI can help compare model options, explain tokenizer behavior, and review code. Ask it to show the smallest working example and list what it is hiding from you.

Exit check:

> Can I explain what enters the model, what comes out, what the loss means, and why the model only sees the top candidate pool?

### Stage 5 — Make experiments reproducible

Before comparing approaches, make it possible to reproduce one run.

Track:

- dataset and split version;
- model and tokenizer;
- seed;
- negative-sampling method;
- learning rate, batch size, and epochs;
- trainable parameter count;
- training and validation metrics;
- checkpoint and evaluation results.

Add a simple configuration file or command-line arguments and save results in a predictable location. Experiment tracking can start as structured JSON or CSV; use a larger tracking tool only when it solves a real problem.

Exit check:

> Can I rerun an experiment later and know exactly what changed between two results?

### Stage 6 — Compare adaptation strategies and learn from failures

Run a small, fair comparison:

1. Frozen encoder with a trainable scoring head.
2. Full fine-tuning.
3. LoRA or another PEFT method.

Keep the dataset, split, evaluation code, and comparison budget consistent. Compare quality, training cost, trainable parameters, and signs of overfitting.

Then run only the most informative ablations:

- less versus more labeled data;
- easy negatives versus hard negatives;
- text-only inputs versus text plus useful metadata.

AI is especially useful as a hypothesis partner here. Give it your result table and ask for competing explanations. Choose the next experiment based on information gained, not on whichever result sounds most impressive.

Exit check:

> Can I explain why the selected method won, or why the evidence is inconclusive?

### Stage 7 — Evaluate honestly

Lock the model and evaluate once on the held-out test queries.

Report:

- baseline and reranker nDCG@10;
- MRR, Recall@10, and Precision@10;
- per-query improvements and regressions;
- bootstrap confidence intervals;
- examples of changed rankings;
- limitations of the labels and test set.

Do not repeatedly tune on the test set. If you discover a problem, document it and create a new split or follow-up experiment.

Ask AI to challenge your evaluation: “What would make this comparison unfair?” Treat every answer as a review checklist, not as proof.

Exit check:

> Can I defend the claim that the model improved retrieval, including uncertainty and cases where it got worse?

### Stage 8 — Optimize and integrate only after quality is understood

Measure the model before optimizing it. Establish a CPU latency baseline, then compare GPU inference, mixed precision, batching, and quantization where available.

For each configuration, record:

- ranking quality;
- p50 and p95/p99 latency;
- throughput;
- memory use;
- hardware and batch size;
- failure modes.

Select a configuration based on the actual product constraint, then integrate it behind the existing search boundary. Add a feature flag or safe fallback if practical, and run an end-to-end API evaluation.

AI can help write benchmark harnesses and deployment checklists. You should decide what to measure, inspect raw timings, and understand why a faster configuration may be unacceptable if it harms relevance.

Exit check:

> Can I explain the quality/latency tradeoff and why the production configuration is appropriate for Strength Atlas?

## Suggested weekly rhythm

Use this rhythm regardless of how long a stage takes:

- **Learn:** read one focused resource and write a short explanation from memory.
- **Predict:** state what you expect before running code.
- **Build:** implement the smallest useful slice.
- **Measure:** save metrics, plots, and examples.
- **Review:** use AI to critique your reasoning and code.
- **Teach:** explain the result in a note or to another person.
- **Choose:** select the next experiment from the evidence.

A productive week may end with a better understanding rather than a new model. That is progress when it prevents an unjustified conclusion.

## Milestones that matter

### Milestone 1: Fundamentals

You can train and validate a small PyTorch model without copying a mysterious training loop.

### Milestone 2: Measurement

You have a labeled retrieval dataset, a frozen split, and a reproducible embedding baseline.

### Milestone 3: First result

You have a working cross-encoder reranker and a fair baseline comparison.

### Milestone 4: Understanding

You can explain errors, negative sampling, adaptation choices, and the evidence behind the result.

### Milestone 5: System

You have measured inference tradeoffs and integrated the selected approach into the real search path.

## What to postpone

Do not add distributed training, Kubernetes, Spark, feature stores, orchestration platforms, or custom CUDA work unless the project develops a genuine need. They can create activity without teaching the central lesson: how to build, evaluate, understand, and serve a useful ML model.

## Definition of learning complete

The plan has done its job when you can answer these questions without relying on buzzwords:

- Why is a cross-encoder useful here?
- What does the model receive and predict?
- How are positives, easy negatives, and hard negatives made?
- Why are the splits done by query?
- Why is nDCG@10 the primary metric?
- What did the baseline get wrong?
- What changed during fine-tuning, and what evidence supports that explanation?
- Did the reranker improve held-out relevance?
- What uncertainty and limitations remain?
- Why was the serving configuration selected?

The strongest final artifact is not a perfect model. It is a reproducible project in which every important choice has a reason, every claim has a measurement, and every AI-assisted shortcut was turned into understanding.

## The loop to keep

```text
Encounter a real Strength Atlas problem
          ↓
Learn the concept needed to investigate it
          ↓
Predict what should happen
          ↓
Implement the smallest experiment
          ↓
Measure and inspect failures
          ↓
Use AI to challenge your reasoning
          ↓
Write down what you learned
          ↓
Choose the next question
```
