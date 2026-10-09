# Feedback: Nebius Token Factory and NVIDIA Nemotron 3 Nano

Lagomy is a CrewAI crew that answers UK supplement questions from NHS, NICE and BNF pages. It runs `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` on Token Factory through CrewAI 1.15.21 (`pyproject.toml`) at `max_tokens=8000` (`src/lagomy/crew.py`).

## 1. Reasoning shares the max_tokens budget (Nebius / NVIDIA)

**What happened.** In our first tool-calling smoke test at `max_tokens=500`, Token Factory returned `content: None`, `finish_reason: "length"` and no tool calls: reasoning used the whole budget before the model acted. In a full crew eval at 3000 tokens (14 September), one answer stopped at 328 characters mid-sentence. The 3000 setting was never committed, and that run's results file was overwritten before a copy was kept, so neither is in the repo. At 8000, answers completed. Reasoning is long: up to 15,478 characters in one logged response, beside empty content (`logs/responses_2026-09-18T195300.jsonl`, captured by `src/lagomy/logged_llm.py`). The limit changes are in commit `8e97e89`.

**Reproduce.** OpenAI client, `NEBIUS_BASE_URL`, the model above, a tool-calling prompt, `max_tokens=500` (`test_nemotron.py` at `4e06b46`).

**Impact.** The API reported the truncation correctly, but the cause did not reach the application layer (see point 2), so at first it looked like a broken model rather than a spent budget. Every call is now over-provisioned to leave room for reasoning. We did not log `usage`, so we cannot say how much of the 8000 reasoning consumes.

**Suggestion.** Document a recommended `max_tokens` for Nemotron reasoning models on tool-calling prompts, and a way to cap reasoning separately from the answer if one exists. Make reasoning token counts easy to find in `usage`, if they are not already reported there.

## 2. Reasoning is invisible in CrewAI's tool-calling path (CrewAI)

**What happened.** Token Factory does return reasoning (point 1). CrewAI 1.15.21's native tool-calling path never fires the step callback before tool calls and hard-codes the thought empty (commit `b50aa64`), so reasoning never surfaces above the provider layer (commit `03fe49f`). Capturing it needed a subclass overriding the private `_get_sync_client` (`src/lagomy/logged_llm.py`), which we parked.

**Impact.** We could not see why Nemotron skipped a search; the 14 September trace was built from search logs alone (commit `e4fe013`).

**Suggestion.** CrewAI: expose provider reasoning on step and LLM-call events. Nebius: document the `reasoning` field name so frameworks map it.

## 3. CrewAI custom-endpoint friction (CrewAI, seen with Token Factory)

**What happened.** On CrewAI 1.14.7, the LiteLLM extra could not be installed. `uv add 'crewai[litellm]'` failed to resolve: CrewAI 1.14.7 requires `openai>=2.30.0` and `python-dotenv>=1.2.2`, while every LiteLLM in its pinned range (`>=1.83.7,<1.84`) requires `openai==2.24.0` and `python-dotenv==1.0.1`. The resolver output was not committed; this is from the terminal. Upgrading to 1.15.21 (commit `8aa8ee3`) removed the need for LiteLLM.

On 1.15.21, CrewAI splits `openai/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` at the first slash and sends `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`. The name fails CrewAI's OpenAI model validation, so the native client is used only if `base_url` is passed in code; otherwise it falls back to LiteLLM (`crewai/llm.py`, installed 1.15.21). YAML `llm:` strings (commit `eecb799`) gave way to `LLM(base_url=...)`.

**Reproduce.** `LLM(model="openai/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")` with only `OPENAI_API_BASE` set raises ImportError "did not match any supported native provider", while listing openai as supported. Adding `base_url=` works (checked locally, no model call).

**Suggestion.** CrewAI: fix the extra's pins, honour `OPENAI_API_BASE` for unknown `openai/` names, and name the failed check in the error. Nebius: publish a CrewAI snippet using `base_url`.

## 4. Shared-endpoint stability notice (Nebius)

**What happened.** The Token Factory console shows a notice that the shared endpoint is meant for testing rather than production, and that its availability and region can change without notice, which would break the base URL. Our live demo depends on that endpoint. For balance, none of the Nemotron runs in `results/*.jsonl` recorded an API error.

**Suggestion.** Repeat the notice in the API docs, not only the console. Give builders a stable base URL or a migration path for demos and early production, and announce changes ahead of time.

## Also worth noting

- **Tool calls returned as text.** In 16 of 276 runs at 8000 tokens, the answer was raw `<tool_call><function=uk_evidence_search>` markup in the content (`results/batch2_nemotron_x10.jsonl` 10/80, `original6_nemotron_x10.jsonl` 3/60, `eval_2026-09-27_0542.jsonl` 2/60, `routing_focus_nemotron_x20.jsonl` 1/40); the other 36 runs, in four smaller early files, contained none. The repo cannot show whether the model or the endpoint's tool parser is at fault.
- **Direct calls worked first time:** completions and tool calling (commit `4e06b46`).
- **Citations.** Nemotron cited a page its searches never returned in 55 of 174 citing runs (`results/FINDINGS.md`, Finding 3).
- **Reassurance.** Told "I feel completely fine now" after 15 iron tablets, it routed to urgent care 5 times in 32 (`results/FINDINGS.md`, Finding 1).
