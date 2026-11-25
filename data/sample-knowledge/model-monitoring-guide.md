# Model Monitoring Guide

Lumenfield Labs, ML Platform team. Applies to every model served in production.

## What we monitor

Every production model has a Grafana dashboard named `model-health`. It shows four panels:
prediction latency, error rate, input data drift, and accuracy on the weekly holdout set.

Prediction latency is measured at the model endpoint. The service level objective is a
95th percentile latency below 300 milliseconds over any one-hour window.

The error rate counts requests that return a server error. It must stay below 1 percent
over any one-hour window.

## Data drift

Input data drift is measured with the Population Stability Index (PSI), computed daily for
each input feature against the training data distribution.

- A PSI below 0.1 means no significant drift.
- A PSI between 0.1 and 0.2 is a warning shown on the dashboard, with no alert.
- A PSI above 0.2 on any feature fires a data drift alert. Data drift alerts are classified
  as SEV2 incidents and page the ML on-call engineer.

When a data drift alert fires, the on-call engineer first opens the `model-health` dashboard
to confirm which features drifted and whether the accuracy panel shows a drop.

## Accuracy and retraining

Accuracy is measured every week on a fresh labelled holdout set. A model must be retrained
when its accuracy drops more than 5 percentage points below the baseline recorded at its
last release. Retraining uses the most recent 12 months of training data.

## Review cadence

The ML on-call engineer reviews every `model-health` dashboard weekly, on Monday morning,
and records the review in the team channel. A monthly model review meeting, held on the
first Tuesday of the month, looks at trends across all models.
