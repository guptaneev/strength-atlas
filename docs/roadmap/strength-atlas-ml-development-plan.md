# Strength Atlas ML Development Plan

## Goal

Turn Strength Atlas from a search/retrieval engineering project into a complete applied machine learning project demonstrating:

- PyTorch model training
- Neural network training loops
- Hugging Face Transformers
- Fine-tuning pretrained models
- LoRA / PEFT
- Information retrieval evaluation
- Experiment tracking
- Statistical validation
- Ablation studies
- GPU inference
- Mixed precision
- Batching
- Quantization
- Latency and throughput benchmarking
- Production model integration

The central research question is:

> **Can a learned cross-encoder reranker significantly improve Strength Atlas search relevance over embedding cosine similarity?**

The final architecture should be:

```text
User Query
    ↓
Embedding Retrieval
    ↓
Top 20–50 Candidates
    ↓
Cross-Encoder Reranker
    ↓
Top 10 Programs
    ↓
API Response
```

The project should be developed in the order below.

---

# Phase 0: Define the Experiment

Before training anything, explicitly define what the ML experiment is trying to prove.

## Research Question

Can a learned cross-encoder reranker improve Strength Atlas search relevance over the existing cosine-similarity retrieval system?

## Primary Metric

Use:

```text
nDCG@10
```

nDCG is useful because relevance can be graded rather than simply correct/incorrect.

## Secondary Metrics

Track:

```text
MRR
Recall@10
Precision@10
```

## Baseline

The existing embedding + cosine similarity retrieval system.

## Candidate Model

A pretrained transformer used as a cross-encoder reranker.

The model receives:

```text
[query, candidate program]
```

and produces:

```text
relevance score
```

## Initial Success Criteria

The reranker should:

1. Improve nDCG@10 over cosine similarity.
2. Avoid significant regression in Recall@10.
3. Produce consistent improvements across test queries.
4. Remain fast enough to use inside the Strength Atlas search API.

The goal is **not** simply to successfully fine-tune a transformer.

The goal is to demonstrate that the learned model improves retrieval.

---

# Phase 1: PyTorch Fundamentals

Before modifying Strength Atlas, build a tiny disposable neural network.

Do not turn this into a separate major project.

Its only purpose is to make sure the PyTorch mechanics are understood before working with transformers.

## Learn

Be able to implement and explain:

```text
torch.Tensor
nn.Module
forward()
Dataset
DataLoader
loss functions
optimizers
backpropagation
model.train()
model.eval()
torch.no_grad()
checkpointing
GPU device handling
```

## Build a Simple Model

For example:

```python
class Classifier(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )

    def forward(self, x):
        return self.network(x)
```

Always reason explicitly about tensor dimensions.

For example:

```python
# x:      [batch_size, input_dim]
# hidden: [batch_size, hidden_dim]
# logits: [batch_size, num_classes]
```

## Write the Training Loop Yourself

Understand every line:

```python
for epoch in range(num_epochs):

    model.train()

    for x, y in train_loader:

        optimizer.zero_grad()

        logits = model(x)

        loss = criterion(logits, y)

        loss.backward()

        optimizer.step()
```

Then implement validation:

```python
model.eval()

with torch.no_grad():
    ...
```

Understand:

- why gradients accumulate
- why `zero_grad()` is necessary
- what `loss.backward()` actually computes
- what `optimizer.step()` changes
- why validation does not calculate gradients
- why `train()` and `eval()` change model behavior

## Add

- train / validation / test split
- model checkpointing
- reproducible seeds
- learning curves
- early stopping
- GPU support

Example:

```python
device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)
```

## Intentionally Create Failure Modes

Experiment with:

- excessively high learning rate
- excessively low learning rate
- very small training set
- excessive model capacity
- too many epochs
- different batch sizes

Observe:

```text
overfitting
underfitting
unstable training
validation divergence
slow convergence
```

## Exit Criterion

Delete the training loop and rebuild it without referencing the original.

You should be able to explain:

```text
forward pass
→ loss
→ backward pass
→ parameter gradients
→ optimizer update
```

without relying on framework magic.

---

# Phase 2: Define the Retrieval Dataset

This is one of the most important parts of the entire project.

The model is only useful if the evaluation dataset is meaningful.

---

## Step 2.1: Define a Document

Determine exactly what Strength Atlas retrieves.

Potential options include:

```text
entire program
program description
individual claim
program + structured metadata
```

Choose one consistent representation.

A document might look like:

```json
{
  "document_id": "program_173",
  "title": "Beginner Powerlifting Program",
  "description": "...",
  "frequency": 4,
  "experience_level": "beginner",
  "goal": "strength"
}
```

---

## Step 2.2: Define Queries

Create realistic user queries.

Examples:

```text
beginner powerlifting program four days per week

bench-focused intermediate powerlifting program

program for someone preparing for their first meet

high-frequency squat program

three-day program for someone with limited time

powerlifting program focused on improving deadlift
```

Queries should describe real user intent rather than artificial keyword combinations.

---

## Step 2.3: Define Relevance

Use graded relevance.

For example:

```text
0 = irrelevant
1 = somewhat useful
2 = relevant
3 = highly relevant
```

A judgment can conceptually look like:

```json
{
  "query_id": "q17",
  "document_id": "p84",
  "relevance": 3
}
```

Graded relevance makes nDCG particularly useful.

---

# Phase 3: Construct Candidate Pools

Do not label every query against every program.

Instead, create a candidate pool for each query.

A good pool contains:

```text
top results from the existing retriever
+
random negatives
+
hard negatives
```

## Positive Example

Query:

```text
beginner 4-day powerlifting program
```

Candidate:

```text
4-day novice strength program
```

## Easy Negative

```text
advanced 6-day bodybuilding specialization
```

## Hard Negative

```text
4-day advanced powerlifting specialization
```

The hard negative contains many relevant words but violates an important constraint.

Hard negatives are particularly valuable because they teach the model to distinguish:

```text
lexically similar
```

from:

```text
actually relevant
```

---

# Phase 4: Freeze Train / Validation / Test Splits

Split by **query**, not by query-document pair.

Example:

```text
70% training queries
15% validation queries
15% test queries
```

Never allow:

```text
query A + document X
```

in training while:

```text
query A + document Y
```

appears in the test set.

That would introduce query leakage.

Once the test set is finalized, treat it as frozen.

Do not repeatedly inspect test performance while tuning models.

Use:

```text
training set
```

for fitting parameters.

Use:

```text
validation set
```

for model selection and experimentation.

Use:

```text
test set
```

once the model is finalized.

---

# Phase 5: Establish the Baseline

Before training any neural model, evaluate the existing retrieval system.

The baseline should be frozen before reranker development.

Evaluate:

```text
nDCG@10
MRR
Recall@10
Precision@10
```

Conceptually, results might look like:

```text
Cosine Similarity Baseline

nDCG@10:     0.681
MRR:         0.714
Recall@10:   0.823
Precision@10: 0.510
```

These values are examples only.

The actual numbers must come from the experiment.

Save enough information to inspect individual rankings:

```text
query
candidate
cosine score
rank
true relevance
```

---

# Phase 6: Baseline Error Analysis

Before building the neural model, understand why the existing system fails.

Manually inspect approximately:

```text
20–30 representative queries
```

Create error categories.

Possible categories:

```text
experience-level mismatch

training-frequency mismatch

goal mismatch

lexical similarity without semantic relevance

multiple-query-constraint failure

important metadata ignored

redundant results

incorrectly ranked partially relevant programs
```

Quantify them where possible.

For example:

```text
Experience mismatch       28%
Frequency mismatch        24%
Multiple constraints      21%
Semantic mismatch         17%
Other                     10%
```

The actual categories should come from observed failures.

This analysis provides the hypothesis for the reranker.

For example:

> Cosine similarity retrieves programs containing relevant concepts but frequently fails to jointly satisfy constraints such as experience level, frequency, and training goal.

That provides a reason to test a cross-encoder.

---

# Phase 7: Build Cross-Encoder Reranker V1

Now build the first real neural ranking model.

Do not start with LoRA.

First understand ordinary transformer fine-tuning.

## Architecture

```text
Query
  +
Candidate Program
        ↓
Tokenizer
        ↓
Transformer Encoder
        ↓
Sequence Representation
        ↓
Scoring Head
        ↓
Relevance Score
```

Conceptually:

```text
[CLS]

beginner powerlifting program four days per week

[SEP]

program information...

[SEP]
```

Output:

```text
relevance score
```

Higher scores represent stronger predicted relevance.

---

# Phase 8: Choose a Small Pretrained Model

Start with a relatively lightweight transformer.

The first goal is rapid experimentation rather than maximum performance.

Possible families include:

```text
MiniLM
DistilBERT
BERT-style cross-encoders
Sentence Transformers cross-encoder checkpoints
```

Choose a model small enough that experiments can be repeated cheaply.

You should learn:

```text
tokenization
attention masks
sequence lengths
pretrained checkpoints
classification heads
optimizer configuration
learning-rate scheduling
transfer learning
```

---

# Phase 9: Build the Training Pipeline

Training should be reproducible.

Important configuration values include:

```text
model checkpoint
learning rate
batch size
number of epochs
maximum sequence length
seed
optimizer
scheduler
```

Example configuration:

```yaml
model: pretrained-cross-encoder
learning_rate: 2e-5
batch_size: 16
epochs: 4
max_length: 256
seed: 42
```

Track:

```text
training loss
validation loss
validation nDCG@10
validation MRR
validation Recall@10
learning rate
epoch
```

Use validation ranking performance rather than training loss alone to select the best checkpoint.

---

# Phase 10: Train Reranker V1

Run the first end-to-end experiment.

The objective is simply:

> Does learned pairwise scoring beat cosine similarity?

Do not immediately run dozens of hyperparameter sweeps.

First establish that the pipeline works.

Inspect:

```text
training loss
validation loss
ranking metrics
individual predictions
failure cases
```

Questions to answer:

```text
Is the model learning?

Does validation performance improve?

Does it overfit?

Are certain query types improving?

Are predictions obviously broken?

```

---

# Phase 11: Add Experiment Tracking

Once the first complete training pipeline works, add experiment tracking.

Use something such as:

```text
Weights & Biases
```

or:

```text
MLflow
```

Weights & Biases is a good default for this project.

Every run should record:

```text
model checkpoint
dataset version
seed
learning rate
batch size
epochs
maximum sequence length
number of trainable parameters
training loss
validation loss
validation nDCG@10
validation MRR
validation Recall@10
runtime
```

Your experiment history should eventually resemble:

| Experiment | Method | LR | Batch | nDCG@10 |
|---|---|---:|---:|---:|
| baseline | cosine | - | - | TBD |
| run-01 | full FT | 2e-5 | 16 | TBD |
| run-02 | full FT | 1e-5 | 16 | TBD |
| run-03 | LoRA | 2e-5 | 16 | TBD |

The point is reproducibility, not maximizing the number of experiments.

---

# Phase 12: Compare Adaptation Strategies

Now compare meaningful training strategies.

---

## Experiment A: Frozen Encoder

Freeze the transformer.

Train only the ranking head.

Conceptually:

```text
Pretrained Transformer
      🔒 frozen
          ↓
Ranking Head
      trainable
```

This provides a cheap transfer-learning baseline.

---

## Experiment B: Full Fine-Tuning

Train the entire transformer.

Measure:

```text
ranking quality
training time
GPU memory
validation behavior
overfitting
```

---

## Experiment C: LoRA / PEFT

Use Parameter-Efficient Fine-Tuning.

Learn:

```text
LoRA
PEFT
adapter layers
rank
alpha
target modules
frozen parameters
trainable parameters
```

Compare LoRA with full fine-tuning.

Questions:

```text
Does LoRA match full fine-tuning quality?

Does it reduce memory usage?

Does it train faster?

Does full fine-tuning overfit more?

How many parameters are actually trainable?
```

The important part is being able to explain why PEFT is useful rather than simply calling the API.

---

# Phase 13: Training-Set-Size Ablation

Run the same model using different amounts of training data.

For example:

```text
25%
50%
75%
100%
```

Keep other important variables fixed.

Measure:

```text
nDCG@10
MRR
Recall@10
```

This answers:

> How label-efficient is the reranker?

A possible result shape might be:

```text
Training Data    nDCG@10

25%              ...
50%              ...
75%              ...
100%             ...
```

Do not invent conclusions before observing the results.

---

# Phase 14: Hard-Negative Ablation

Compare:

```text
random negatives only
```

against:

```text
random negatives + hard negatives
```

Keep everything else as constant as reasonably possible.

Question:

> Do hard negatives help the reranker distinguish superficially similar but genuinely different programs?

This is particularly relevant for Strength Atlas because many programs will share powerlifting terminology while differing significantly in:

```text
experience level
frequency
goal
volume
specialization
```

---

# Phase 15: Metadata Ablation

Compare program representations.

## Version A

```text
program text only
```

## Version B

```text
program text
+
experience level
+
days per week
+
training goal
+
other useful metadata
```

Question:

> Does explicit structured metadata improve ranking beyond natural-language program descriptions?

This makes the project more domain-specific and less like a generic transformer tutorial.

---

# Phase 16: Model Selection

After the meaningful experiments are complete, select the final model using the **validation set**.

Do not choose the model based on test-set performance.

Consider:

```text
nDCG@10
MRR
Recall@10
stability
training cost
inference cost
model size
```

The highest-scoring model is not automatically the best model if the gain is negligible and inference cost is dramatically worse.

Document the reasoning.

---

# Phase 17: Final Test Evaluation

Freeze the model.

Then evaluate once against the held-out test set.

Compare:

```text
Cosine Baseline
vs
Cross-Encoder Reranker
```

Report:

```text
nDCG@10
MRR
Recall@10
Precision@10
```

For example:

```text
                     Cosine      Reranker

nDCG@10               TBD          TBD
MRR                    TBD          TBD
Recall@10              TBD          TBD
Precision@10           TBD          TBD
```

Do not replace `TBD` until real experimental results exist.

---

# Phase 18: Bootstrap Confidence Intervals

Do not report only point estimates.

Estimate uncertainty across test queries.

Use bootstrap resampling to calculate a confidence interval for the difference between the reranker and baseline.

For example:

```text
Δ nDCG@10 = reranker - baseline
```

Then estimate:

```text
95% bootstrap confidence interval
```

A result might eventually look like:

```text
Δ nDCG@10 = +0.067
95% CI = [+0.041, +0.089]
```

Those numbers are illustrative only.

The important question is:

> Is the improvement consistent across queries rather than being driven by a handful of examples?

---

# Phase 19: Post-Training Error Analysis

Repeat the earlier error analysis.

Use the same categories where possible.

Compare something like:

```text
                       Baseline    Reranker

Experience mismatch      TBD         TBD
Frequency mismatch       TBD         TBD
Multiple constraints     TBD         TBD
Semantic mismatch        TBD         TBD
```

This lets you explain *why* performance changed.

Look for findings such as:

```text
The reranker performs especially well on multi-constraint queries.

The reranker improves experience-level matching.

Simple keyword-heavy queries show little improvement.

Certain program categories remain difficult.

```

Only claim findings actually supported by the experiment.

---

# Phase 20: Create an Inference Benchmark

Once the final model is frozen, optimize inference.

Do not mix training experimentation with systems optimization.

Build a repeatable benchmark.

Measure:

```text
p50 latency
p95 latency
p99 latency
throughput
memory usage
model size
ranking quality
```

Always include ranking quality because an optimization that dramatically reduces model quality is not useful.

---

# Phase 21: CPU Baseline

Measure the simplest configuration first.

For example:

```text
CPU
FP32
batch size = 1
```

Record:

```text
p50
p95
p99
queries / second
memory
```

This becomes the inference baseline.

---

# Phase 22: GPU Benchmark

Run the same workload on GPU.

Start with:

```text
GPU
FP32
batch size = 1
```

Compare:

```text
CPU latency
GPU latency
CPU throughput
GPU throughput
```

Learn when GPU acceleration actually helps.

For tiny workloads, transfer overhead can matter.

Measure rather than assume.

---

# Phase 23: Mixed Precision

Benchmark:

```text
FP32
vs
FP16 / BF16
```

Measure:

```text
latency
throughput
memory
ranking quality
```

Understand why lower precision can improve GPU performance.

---

# Phase 24: Batching

Benchmark multiple batch sizes.

For example:

```text
1
4
8
16
32
```

Measure:

```text
batch size
p50 latency
p99 latency
queries / second
GPU memory
```

Understand the tradeoff:

```text
larger batch
→ better throughput
→ potentially worse per-request latency
```

This distinction matters.

Latency and throughput are not the same metric.

---

# Phase 25: Quantization

Test an appropriate quantization approach for the final model/runtime.

Potentially compare:

```text
FP32
FP16
INT8
```

Measure:

```text
model size
memory
p50 latency
p99 latency
throughput
nDCG@10
```

The key question is:

> How much inference efficiency can be gained before ranking quality materially degrades?

Do not optimize toward a predetermined outcome.

---

# Phase 26: Choose the Production Configuration

Compare every inference strategy.

Conceptually:

| Configuration | p50 | p99 | Throughput | Memory | nDCG@10 |
|---|---:|---:|---:|---:|---:|
| CPU FP32 | TBD | TBD | TBD | TBD | TBD |
| GPU FP32 | TBD | TBD | TBD | TBD | TBD |
| GPU mixed precision | TBD | TBD | TBD | TBD | TBD |
| batched | TBD | TBD | TBD | TBD | TBD |
| quantized | TBD | TBD | TBD | TBD | TBD |

Choose the configuration based on the desired balance between:

```text
quality
latency
throughput
memory
cost
```

---

# Phase 27: Integrate the Model Into Strength Atlas

Once training and benchmarking are complete, integrate the model into the real search pipeline.

Use two-stage retrieval.

```text
User Query
    ↓
Embedding Retriever
    ↓
Top ~25 Candidates
    ↓
Cross-Encoder Reranker
    ↓
Top 10
    ↓
API Response
```

The embedding model performs:

```text
fast candidate generation
```

The cross-encoder performs:

```text
slower but more precise ranking
```

Do not use the cross-encoder unnecessarily against the entire corpus for every request.

---

# Phase 28: Production Evaluation

After integration, verify that offline gains survive in the actual application.

Test:

```text
API latency
reranking latency
end-to-end latency
failure handling
empty results
long queries
long documents
batch behavior
model loading
concurrent requests
```

Make sure the ML system does not break the existing engineering quality of Strength Atlas.

---

# Phase 29: Final Results

The finished project should answer several concrete questions.

## Retrieval

```text
Did the reranker beat cosine similarity?
```

## Statistical Rigor

```text
Was the improvement consistent across test queries?
```

## Data

```text
How much labeled training data was required?
```

## Negative Sampling

```text
Did hard negatives help?
```

## Domain Information

```text
Did explicit program metadata improve ranking?
```

## Fine-Tuning

```text
How did frozen, full-fine-tuning, and LoRA approaches compare?
```

## Systems

```text
What was the latency / throughput tradeoff?
```

## Optimization

```text
What effect did batching, mixed precision, and quantization have?
```

These questions are the intellectual core of the project.

---

# Recommended Development Order

Follow this order.

Do not jump immediately to the flashy parts.

```text
1. PyTorch fundamentals

2. Define retrieval task

3. Define relevance labels

4. Construct candidate pools

5. Freeze train / validation / test splits

6. Run cosine baseline

7. Analyze baseline failures

8. Build cross-encoder V1

9. Train first model

10. Add experiment tracking

11. Compare frozen vs full fine-tuning vs LoRA

12. Run training-set-size ablation

13. Run hard-negative ablation

14. Run metadata ablation

15. Select final model using validation data

16. Evaluate frozen test set

17. Bootstrap confidence intervals

18. Repeat error analysis

19. Benchmark CPU inference

20. Benchmark GPU inference

21. Test mixed precision

22. Test batching

23. Test quantization

24. Select production configuration

25. Integrate two-stage retrieval

26. Benchmark end-to-end system

27. Document results

28. Update resume
```

---

# Suggested Six-Week Schedule

The exact timeline is flexible.

The dependency order matters more than completing each stage within exactly one week.

---

## Week 1: PyTorch + Dataset Design

### Goal

Become comfortable training a neural model and formalize the Strength Atlas ML task.

### Tasks

- implement `nn.Module`
- write training loop
- write validation loop
- use `Dataset`
- use `DataLoader`
- use GPU
- experiment with overfitting
- define document representation
- define query representation
- define relevance scale
- inspect current evaluation data

### End-of-Week Requirement

You can independently write and explain a PyTorch training loop.

---

# Week 2: Retrieval Benchmark

### Goal

Create a trustworthy evaluation dataset.

### Tasks

- create realistic queries
- create candidate pools
- identify hard negatives
- create relevance judgments
- freeze query-level splits
- implement nDCG
- implement MRR
- implement Recall@10
- establish cosine baseline
- perform baseline error analysis

### End-of-Week Requirement

You have a frozen benchmark and baseline score.

---

# Week 3: First Neural Reranker

### Goal

Train the first model that can potentially beat the baseline.

### Tasks

- select pretrained transformer
- implement tokenization
- create query-document inputs
- implement training
- implement validation
- add checkpointing
- inspect training curves
- compare against cosine similarity

### End-of-Week Requirement

A cross-encoder successfully trains and produces ranked results.

---

# Week 4: Fine-Tuning + Experiments

### Goal

Turn the working model into rigorous ML experimentation.

### Tasks

- add W&B or MLflow
- frozen encoder experiment
- full fine-tuning experiment
- LoRA / PEFT experiment
- compare trainable parameters
- compare GPU memory
- compare validation performance
- training-size ablation
- hard-negative ablation
- metadata ablation

### End-of-Week Requirement

You understand which modeling decisions improve performance and why.

---

# Week 5: Evaluation + Statistics

### Goal

Determine whether the model genuinely works.

### Tasks

- select final model using validation set
- freeze model
- evaluate test set
- compute nDCG@10
- compute MRR
- compute Recall@10
- compute Precision@10
- bootstrap metric differences
- generate confidence intervals
- repeat error analysis
- determine which query types improve most

### End-of-Week Requirement

You have a defensible answer to:

> Did the learned reranker actually beat the existing system?

---

# Week 6: Inference Optimization + Deployment

### Goal

Turn the trained model into a production ML system.

### Tasks

- CPU benchmark
- GPU benchmark
- mixed-precision benchmark
- batching benchmark
- quantization benchmark
- quality-vs-performance comparison
- integrate reranker into search
- benchmark end-to-end API
- finalize technical results

### End-of-Week Requirement

Strength Atlas contains a trained, evaluated, optimized neural reranker in its real search pipeline.

---

# Project Skill Checklist

Do not consider a skill acquired merely because its library was imported.

Each skill should have corresponding evidence.

## PyTorch

Evidence:

```text
Custom training and evaluation pipeline.
```

## Neural Networks

Evidence:

```text
Understands forward pass, loss, backpropagation, optimizer updates, training dynamics, and overfitting.
```

## Transformers

Evidence:

```text
Uses and understands a pretrained transformer for cross-encoding.
```

## Transfer Learning

Evidence:

```text
Adapts pretrained model to domain-specific retrieval.
```

## Hugging Face

Evidence:

```text
Uses tokenizer, model checkpoints, and transformer training pipeline.
```

## PEFT / LoRA

Evidence:

```text
Compares parameter-efficient adaptation against alternative fine-tuning strategies.
```

## Experiment Tracking

Evidence:

```text
Reproducible experiment runs with configs and metrics.
```

## Information Retrieval

Evidence:

```text
nDCG, MRR, Recall, Precision, candidate generation, reranking.
```

## Statistical Rigor

Evidence:

```text
Bootstrap confidence intervals over held-out queries.
```

## Ablation Studies

Evidence:

```text
Training-set size, negative sampling, and metadata experiments.
```

## GPU Inference

Evidence:

```text
CPU/GPU benchmark comparison.
```

## Mixed Precision

Evidence:

```text
Measured quality/performance effect of lower-precision inference.
```

## Batching

Evidence:

```text
Measured throughput-latency tradeoff across batch sizes.
```

## Quantization

Evidence:

```text
Measured quality, memory, and inference effects.
```

## Production ML

Evidence:

```text
Two-stage retrieval integrated into the Strength Atlas API.
```

---

# What Not to Add

Avoid turning this project into an infrastructure checklist.

Do not prioritize:

```text
Kubernetes
Ray
Spark
distributed training
multi-node GPUs
Airflow
feature stores
KServe
custom CUDA kernels
large-scale distributed inference
```

unless the actual project eventually creates a genuine need for them.

Strength Atlas should primarily close the ML-modeling gap.

The most valuable progression is:

```text
train
→ evaluate
→ understand
→ optimize
→ deploy
```

---

# Minimum Viable Success

The entire plan does not need to be completed before the project becomes valuable.

There are four major checkpoints.

---

## Checkpoint 1

```text
I can train a neural model myself in PyTorch.
```

Skills gained:

```text
nn.Module
training loops
backpropagation
optimization
validation
```

---

## Checkpoint 2

```text
I trained a cross-encoder reranker that beats the existing cosine-similarity baseline on held-out queries.
```

This is the most important checkpoint.

Once this is achieved, the project is already strong enough to materially improve the ML portion of the resume.

---

## Checkpoint 3

```text
I demonstrated through confidence intervals, error analysis, and ablations that the improvement is meaningful and understand where it comes from.
```

At this point the project begins to look much more like research-quality applied ML work.

---

## Checkpoint 4

```text
I optimized and deployed the trained model inside the real Strength Atlas search system.
```

This completes the ML engineering lifecycle.

---

# Final Expected Technical Story

By the end of the project, you should be able to explain something similar to:

> Strength Atlas originally used embedding cosine similarity to retrieve powerlifting programs. I built a labeled ranking benchmark and found that the baseline frequently struggled with queries containing multiple constraints such as experience level, training frequency, and goal. I trained a transformer cross-encoder reranker in PyTorch and compared frozen transfer learning, full fine-tuning, and LoRA. I evaluated the models using nDCG@10, MRR, and Recall@10 on held-out queries, then used bootstrap confidence intervals and ablation studies to determine whether the improvements were consistent and what drove them. Finally, I benchmarked the model across CPU and GPU inference, mixed precision, batching, and quantization before integrating the selected model into a two-stage FastAPI retrieval pipeline.

The exact story should ultimately use the real findings rather than predetermined conclusions.

---

# Final Resume Target

Do **not** write these bullets until the corresponding measurements actually exist.

The final Strength Atlas section should eventually have the structure:

```text
Strength Atlas | PyTorch, Hugging Face, FastAPI, PostgreSQL

• Trained a transformer cross-encoder reranker on [X] labeled
  query-document pairs, improving nDCG@10 from [X] to [Y]
  over a cosine-similarity retrieval baseline.

• Fine-tuned [MODEL] using [METHOD] and evaluated retrieval
  quality using nDCG, MRR, bootstrap confidence intervals,
  and training-set-size / hard-negative ablations.

• Optimized neural reranking with [mixed precision /
  quantization / batching], reducing p99 latency from [X]
  to [Y] while increasing throughput by [Z]×.
```

The values must come from actual experiments.

---

# Final Completion Criteria

The project is complete when you can confidently answer all of the following without relying on buzzwords:

### Modeling

- Why use a cross-encoder?
- Why not only embeddings?
- What does the transformer receive as input?
- What is the model predicting?
- What loss is being optimized?
- How does backpropagation update the model?

### Fine-Tuning

- Why start from a pretrained model?
- Why use LoRA?
- How did LoRA compare with full fine-tuning?
- How many parameters were trainable?
- Did either method overfit?

### Data

- How were queries created?
- How was relevance defined?
- What is a hard negative?
- Why were splits done by query?
- How was leakage prevented?

### Evaluation

- Why nDCG?
- What does MRR measure?
- What does Recall@10 measure?
- Why isn't generic "accuracy" sufficient?
- What was the baseline?
- How much did the model improve?

### Statistics

- Why use confidence intervals?
- How were they calculated?
- Was the observed improvement consistent?
- What did the ablations reveal?

### Systems

- Why use two-stage retrieval?
- What is the latency-throughput tradeoff?
- What happened when batch size increased?
- What did mixed precision change?
- What did quantization change?
- Why was the final serving configuration selected?

If those questions can be answered confidently from work actually performed in Strength Atlas, the project has accomplished its purpose.

---

# Guiding Rule

Whenever there is a choice between:

```text
learning another ML concept theoretically
```

and:

```text
using that concept to answer the next real question in Strength Atlas
```

prefer the second.

The development loop should remain:

```text
Encounter problem
      ↓
Learn necessary concept
      ↓
Implement it
      ↓
Measure result
      ↓
Understand failure
      ↓
Run next experiment
```

That is the central development philosophy for the project.