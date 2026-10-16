"""Chat prompts and extraction of the SQL answer from model output.

The same template and the same extraction are used for every condition (C1, C2, C3).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

import sqlparse

SYSTEM_PROMPT = (
    "You translate questions into SQLite queries. Given a database schema and a question, "
    "answer with exactly one SQLite query and nothing else."
)

Message = dict[str, str]


@dataclass(frozen=True)
class Shot:
    schema: str
    question: str
    query: str


def user_message(schema: str, question: str) -> str:
    return f"Database schema:\n{schema}\n\nQuestion: {question}"


def build_messages(schema: str, question: str, shots: Sequence[Shot] = ()) -> list[Message]:
    """System message, optional few-shot turns, then the question. No answer appended."""
    messages: list[Message] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for shot in shots:
        messages.append({"role": "user", "content": user_message(shot.schema, shot.question)})
        messages.append({"role": "assistant", "content": shot.query})
    messages.append({"role": "user", "content": user_message(schema, question)})
    return messages


def training_messages(schema: str, question: str, query: str) -> list[Message]:
    """Prompt plus the gold answer. Loss is computed on the assistant turn only."""
    return [*build_messages(schema, question), {"role": "assistant", "content": query}]


_FENCE = re.compile(r"```(?:[a-zA-Z]+)?\s*\n?(.*?)```", re.DOTALL)


def extract_sql(text: str) -> str:
    """First fenced block if any, else the whole text; then the first SQL statement."""
    match = _FENCE.search(text)
    body = match.group(1) if match else text
    body = body.strip()
    if body.lower().startswith("sql\n"):
        body = body[4:]
    statements = [s.strip() for s in sqlparse.split(body) if s.strip()]
    if not statements:
        return ""
    return statements[0].rstrip(";").strip()
