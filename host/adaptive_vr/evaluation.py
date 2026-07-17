from __future__ import annotations

from dataclasses import dataclass

from .taxonomy import StudentState


@dataclass(frozen=True, slots=True)
class ClassMetrics:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    accuracy: float
    macro_f1: float
    by_class: dict[StudentState, ClassMetrics]
    confusion: dict[StudentState, dict[StudentState, int]]


def classification_report(
    truth: list[StudentState], predicted: list[StudentState]
) -> EvaluationReport:
    if len(truth) != len(predicted) or not truth:
        raise ValueError("truth and predicted must have equal non-zero length")
    matrix = {
        actual: {guess: 0 for guess in StudentState}
        for actual in StudentState
    }
    for actual, guess in zip(truth, predicted, strict=True):
        matrix[actual][guess] += 1
    metrics: dict[StudentState, ClassMetrics] = {}
    for state in StudentState:
        tp = matrix[state][state]
        fp = sum(matrix[actual][state] for actual in StudentState if actual != state)
        fn = sum(matrix[state][guess] for guess in StudentState if guess != state)
        support = sum(matrix[state].values())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        metrics[state] = ClassMetrics(precision, recall, f1, support)
    accuracy = sum(actual == guess for actual, guess in zip(truth, predicted, strict=True)) / len(truth)
    supported = [metric.f1 for metric in metrics.values() if metric.support]
    macro_f1 = sum(supported) / len(supported) if supported else 0.0
    return EvaluationReport(accuracy, macro_f1, metrics, matrix)

