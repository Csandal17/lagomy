# Which model produced each results file

Files written before commit 2ad7129 have no "model" field. All were run on
eval/expanded-guardrails, whose crew.py was then hard-coded to
openai/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B via Nebius, max_tokens=8000.

- eval_2026-09-25_1809.jsonl: Nemotron. Original six cases x2.
- eval_2026-09-26_1250.jsonl: Nemotron. route_overdose x10.
  Commit a08087b's message says "on Sonnet". That is wrong.
- eval_2026-09-26_1618.jsonl: Nemotron. Batch 1 x2.
- eval_2026-09-26_1647.jsonl: Nemotron. Batch 1 x10, stopped partway.

Files written after 2ad7129 record the model on every line:

- batch1_sonnet46_x10.jsonl, batch2_sonnet46_x10.jsonl,
  original6_sonnet46_x10.jsonl: anthropic/claude-sonnet-4-6, x10.
- subset_opus55_x10.jsonl: anthropic/claude-opus-5-5, 8-case routing
  and bait subset, x10.
  