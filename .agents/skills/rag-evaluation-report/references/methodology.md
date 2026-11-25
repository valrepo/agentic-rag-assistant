# Evaluation methodology (EM-001 to EM-007)

Source of truth: `specs/spec.md`, section "Evaluation methodology".

## EM-001 Metrics serve decisions

The primary metric is MC-014 (correctness against expected answer points). Its guardrails
are MC-013 (unsupported-claim rate), MC-015 (abstention quality), MC-011 (citation
validity), MC-022 (end-to-end latency), and MC-023 (tokens). Every reported metric states
the decision it supports (column "Decision supported", from the metrics file).

## EM-002 Relevance granularity

Retrieval relevance is judged at document level: a chunk is relevant if it comes from an
expected source. The report must say this is optimistic (a chunk from the right file may
not contain the answer) and that MC-006 and MC-007 need passage-level labels.

## EM-003 Correctness on answer points, not word overlap

Correctness is measured against the expected answer points. BLEU, ROUGE, or any n-gram
overlap score must not be used: they can reward an answer that says the opposite.

## EM-004 Evaluation layers

Deterministic script metrics first; human labels for the metrics that need judgement. No
LLM judge in this version. If one is added later: pin its model, version, and prompt; use a
model family different from the answering model; label its scores "uncalibrated" until its
agreement with human labels has been measured.

## EM-005 Small samples

- Every rate shows numerator and denominator; averaged metrics show per-question values
  and n.
- Below 10 questions, write rates as counts (for example "3/4"), not percentages, and
  describe results as indicative.
- Latency: median and maximum; p95 only when n is at least 20; never a mean alone.
- Never declare two runs different on fewer than 10 questions; with more, compare them
  question by question (paired).

## EM-006 Objectives

Each success criterion with a target (SC-003 to SC-008) is reported as target, measured
value, and verdict (met, not met, not measurable), from `success_criteria` in the metrics
file.

## EM-007 Slices and pitfalls

- Report per question category (`per_category` in the metrics file) as well as overall.
- Never mix fake-model and real-model runs in one metric; fake runs go to their own section.
- If the evaluation questions were used to tune prompts or parameters, say so (see
  `evaluation/README.md`, "Tuning disclosure"): the scores are then optimistic.
