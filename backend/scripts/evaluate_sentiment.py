"""Optional sentiment evaluation.

Usage (PowerShell):
    python scripts/evaluate_sentiment.py --dataset data/sentiment_eval.jsonl

Dataset format: one JSON object per line with "text" and "label"
(Positive | Neutral | Negative).

If no dataset is configured the script reports that honestly and exits -
DRISHTI never prints invented accuracy, precision, recall or F1 numbers.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analytics import sentiment  # noqa: E402

LABELS = ("Positive", "Neutral", "Negative")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/sentiment_eval.jsonl")
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

    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    correct = 0

    for row in rows:
        predicted = sentiment.analyze(row["text"]).label
        actual = row["label"]
        if predicted == actual:
            correct += 1
            tp[actual] += 1
        else:
            fp[predicted] += 1
            fn[actual] += 1

    print(f"Engine: {sentiment.ENGINE}")
    print(f"Samples: {len(rows)}")
    print(f"Accuracy: {correct / len(rows):.3f}")
    f1s = []
    for label in LABELS:
        precision = tp[label] / max(tp[label] + fp[label], 1)
        recall = tp[label] / max(tp[label] + fn[label], 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-9)
        f1s.append(f1)
        print(f"  {label:<9} precision={precision:.3f} recall={recall:.3f} f1={f1:.3f}")
    print(f"Macro-F1: {sum(f1s) / len(f1s):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
