"""Optional retrieval / grounding evaluation for the analyst assistant.

Usage (PowerShell):
    python scripts/evaluate_rag.py --dataset data/rag_eval.jsonl --watch ai-regulation-india

Dataset format: one JSON object per line with
    {"question": "...", "expect_answer": true, "relevant_topics": ["Data Privacy"]}

Reports retrieval relevance, answer grounding, citation validity and refusal
behaviour against the configured dataset. With no dataset the script says so
instead of printing invented benchmark numbers.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import schemas  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Watch  # noqa: E402
from app.services import assistant  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/rag_eval.jsonl")
    parser.add_argument("--watch", default="ai-regulation-india")
    args = parser.parse_args()

    path = Path(args.dataset)
    if not path.exists():
        print("Evaluation dataset not configured.")
        print(f"Expected a labelled JSONL file at: {path}")
        return 0

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        print("Evaluation dataset not configured (file is empty).")
        return 0

    with SessionLocal() as db:
        watch = db.get(Watch, args.watch)
        if watch is None:
            print(f"Watch '{args.watch}' not found. Seed the demo dataset first.")
            return 1

        grounded = refused = citation_ok = relevant = correct_behaviour = 0
        for row in rows:
            result = assistant.answer(db, watch, schemas.AssistantQuery(question=row["question"]))
            expect = bool(row.get("expect_answer", True))
            if result.grounded:
                grounded += 1
                if result.citations:
                    citation_ok += 1
                topics = set(row.get("relevant_topics", []))
                if not topics or any(t.lower() in result.answer.lower() for t in topics):
                    relevant += 1
            else:
                refused += 1
            if result.grounded == expect:
                correct_behaviour += 1

        total = len(rows)
        print(f"Provider: {assistant.provider_name()}")
        print(f"Questions: {total}")
        print(f"Answered with grounding: {grounded}")
        print(f"Refusals (insufficient evidence): {refused}")
        print(f"Answers carrying validated citations: {citation_ok}")
        print(f"Retrieval relevance (expected topic present): {relevant}")
        print(f"Correct answer/refusal behaviour: {correct_behaviour}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
