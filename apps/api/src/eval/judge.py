"""Optional LLM-as-judge for answer faithfulness/relevance.

Disabled by default. The runner only invokes a judge when one is passed
explicitly. The CLI builds this judge ONLY when both:
    - the user passes `--llm-judge`, AND
    - LLM_API_KEY is present in the environment.

The judge uses the same provider as the production agent (via core.providers),
so we never introduce a second secret. We never include or echo the API key
in logs or report output.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


_JUDGE_PROMPT = """You are an evaluator scoring a RAG answer.

Question:
{question}

Reference answer (gold):
{expected}

Candidate answer:
{candidate}

Retrieved context (may be partial):
{context}

Score the candidate from 0.0 to 1.0 considering:
1. Faithfulness - does the candidate stay grounded in the retrieved context?
2. Correctness - does it match the reference answer's key facts?
3. Relevance - does it answer the question?

Respond with strict JSON: {{"score": <float 0..1>, "reasoning": "<one sentence>"}}.
"""


async def make_openai_judge(model: Optional[str] = None) -> Optional[object]:
    """Build a judge_fn closure backed by the project's LLM provider.

    Returns None when the environment cannot supply an LLM (missing key, etc.).
    The function imports lazily so the harness has no hard dependency on
    pydantic_ai during unit tests.
    """
    try:
        from pydantic_ai import Agent

        from src.core.providers import get_llm_model
    except Exception as e:  # noqa: BLE001
        logger.warning("llm_judge_unavailable: %s", e)
        return None

    try:
        llm_model = get_llm_model() if model is None else get_llm_model()
    except Exception as e:  # noqa: BLE001
        logger.warning("llm_judge_provider_init_failed: %s", e)
        return None

    agent = Agent(llm_model, system_prompt="You are a strict, terse evaluator.")

    async def _judge(question: str, expected: str, answer: str, context: str) -> tuple[float, str]:
        prompt = _JUDGE_PROMPT.format(
            question=question.strip(),
            expected=expected.strip(),
            candidate=answer.strip(),
            context=(context or "").strip()[:8000],
        )
        result = await agent.run(prompt)
        raw = getattr(result, "output", None) or getattr(result, "data", "") or ""
        score, reasoning = _parse_judge_output(str(raw))
        return score, reasoning

    return _judge


def _parse_judge_output(raw: str) -> tuple[float, str]:
    """Parse a JSON judge response, falling back to a regex score scrape."""
    text = raw.strip()
    # Try strict JSON first.
    try:
        obj = json.loads(text)
        score = float(obj.get("score", 0.0))
        reasoning = str(obj.get("reasoning", ""))[:500]
        return _clamp01(score), reasoning
    except Exception:  # noqa: BLE001
        pass

    # Fallback: extract first JSON object substring.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            score = float(obj.get("score", 0.0))
            reasoning = str(obj.get("reasoning", ""))[:500]
            return _clamp01(score), reasoning
        except Exception:  # noqa: BLE001
            pass

    # Last resort: pull the first float.
    num = re.search(r"[01](?:\.\d+)?", text)
    if num:
        return _clamp01(float(num.group(0))), text[:200]
    return 0.0, "judge_parse_failed"


def _clamp01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return max(0.0, min(1.0, x))


__all__ = ["make_openai_judge"]
