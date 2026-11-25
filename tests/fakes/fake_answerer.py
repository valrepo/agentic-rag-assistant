"""Deterministic extractive "model" driving the StubLLM through the two-agent crew.

- Retriever call: returns a ReAct tool call to `search_knowledge_base` with the question.
- Answer/Verifier call: reads the chunks in its context. A chunk counts as evidence only if
  it shares at least two content words with the question (a deterministic stand-in for the
  model's sufficiency judgement). Without evidence it reports insufficient evidence;
  otherwise it cites the best evidence chunk of up to two distinct files, using the first
  sentence of each chunk as the statement.

Used by the automated tests and by the fake evaluation run (plan decision 5).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.crew import NO_EVIDENCE
from tests.fakes.fake_embeddings import content_words
from tests.fakes.stub_llm import StubLLM, prompt_text, tool_call

MIN_SHARED_WORDS = 2

_QUESTION = re.compile(r"the user's question: (.+)")
_CHUNK = re.compile(
    r"chunk_id: ([0-9a-f]{12}-\d+) \| file: ([^|\n]+?)(?: \| page: \d+)? \| score: [-0-9.]+\n"
    r"<document>\n(.*?)\n</document>",
    re.DOTALL,
)


def _text(messages: Any) -> str:
    return prompt_text({"messages": messages})


def _first_sentence(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s", " ".join(text.split()), maxsplit=1)[0]
    return sentence[:300]


def make_responder(
    extra_citation: str | None = None,
    fail_with: Exception | None = None,
    max_files: int = 2,
) -> Callable[[Any, Any], Any]:
    def responder(messages: Any, response_model: Any) -> Any:
        if fail_with is not None:
            raise fail_with
        prompt = _text(messages)
        is_answer_call = (
            response_model is not None or NO_EVIDENCE in prompt or "<document>" in prompt
        )
        if not is_answer_call:
            match = _QUESTION.search(prompt)
            query = match.group(1).strip() if match else ""
            return tool_call("search_knowledge_base", {"query": query})
        if NO_EVIDENCE in prompt:
            return {"sufficient_evidence": False, "statements": [], "uncertain": []}
        match = _QUESTION.search(prompt)
        question_words = content_words(match.group(1)) if match else set()
        statements = []
        seen_files: set[str] = set()
        for chunk_id, source_file, text in _CHUNK.findall(prompt):
            if source_file in seen_files:
                continue
            if len(question_words & content_words(text)) < MIN_SHARED_WORDS:
                continue
            seen_files.add(source_file)
            statements.append({"text": _first_sentence(text), "chunk_ids": [chunk_id]})
            if len(seen_files) >= max_files:
                break
        if extra_citation and statements:
            statements[0]["chunk_ids"].append(extra_citation)
        return {
            "sufficient_evidence": bool(statements),
            "statements": statements,
            "uncertain": [],
        }

    return responder


def make_fake_llm(**kwargs: Any) -> StubLLM:
    return StubLLM(responder=make_responder(**kwargs))
