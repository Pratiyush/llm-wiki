---
project: demo-ml-pipeline
topics: [python, machine-learning, distilbert, transformers, huggingface, wandb, training, fine-tuning]
description: "DistilBERT fine-tuning pipeline — data preparation, HuggingFace Trainer loop, W&B logging, and evaluation. Uses the classic transformers + datasets stack."
homepage: "https://example.com/demo-ml-pipeline"
---

# demo-ml-pipeline

Reference project for the ML fine-tuning track. Shards raw text into
a `datasets` dataset, fine-tunes `distilbert-base-uncased` with the
HuggingFace `Trainer`, and logs to Weights & Biases. Demonstrates a
full training loop with learning-rate warmup, early stopping, and a
best-F1 checkpoint callback.

## Connections

- [[Python]]
- [[DistilBERT]]
- [[HuggingFaceTransformers]]
- [[WeightsAndBiases]]
