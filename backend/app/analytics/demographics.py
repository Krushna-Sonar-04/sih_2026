"""Aggregate-only demographic profiling with a minimum reporting threshold.

No individual demographic label is ever stored or returned.
"""
from __future__ import annotations

from dataclasses import dataclass

DIMENSIONS = ("age_cohort", "region", "language", "professional_interest")
SUPPRESSED_MESSAGE = "Cohort too small to report."


@dataclass
class CohortValue:
    cohort: str
    percentage: float
    reportable: bool
    note: str = ""


def aggregate(rows: list, min_percentage: float = 5.0) -> dict[str, list[CohortValue]]:
    """Group stored demographic_aggregate rows by dimension and apply the threshold."""
    grouped: dict[str, list[CohortValue]] = {dim: [] for dim in DIMENSIONS}
    for row in rows:
        reportable = row.percentage >= min_percentage
        grouped.setdefault(row.dimension, []).append(
            CohortValue(
                cohort=row.cohort,
                percentage=round(row.percentage, 1) if reportable else 0.0,
                reportable=reportable,
                note="" if reportable else SUPPRESSED_MESSAGE,
            )
        )
    for dimension, values in grouped.items():
        values.sort(key=lambda v: -v.percentage)
    return grouped
