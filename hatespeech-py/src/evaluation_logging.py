
import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, TextIO


FIELDNAMES = [
    "record_type",
    "run_id",
    "model",
    "item_id",
    "artifact_id",
    "message_type",
    "start_time_utc",
    "end_time_utc",
    "processing_time_ms",
    "batch_start_time_utc",
    "batch_end_time_utc",
    "batch_processing_time_ms",
    "char_count",
    "word_count",
    "token_count",
    "predicted_is_hate",
    "hate_score",
    "label_name",
    "ground_truth_is_hate",
    "manual_is_hate",
    "confusion_class",
    "text",
    "notes",
    "processed_items",
    "total_runtime_ms",
    "min_processing_time_ms",
    "max_processing_time_ms",
    "avg_processing_time_ms",
    "avg_char_count",
    "avg_word_count",
    "avg_token_count",
    "tp",
    "fn",
    "fp",
    "tn",
]


def resolve_evaluation_log_path(log_file: Optional[str], explicit_path: Optional[str]) -> Path:
    if explicit_path and explicit_path.strip():
        return Path(explicit_path)
    if log_file and log_file.strip():
        log_path = Path(log_file).expanduser().resolve()
        match = re.fullmatch(r"hatespeech_(\d{8}_\d{6})\.log", log_path.name)
        if match:
            return log_path.with_name(f"evaluation_{match.group(1)}.csv")
        return log_path.with_name("evaluation.csv")
    return Path("logs") / "evaluation.csv"


def open_evaluation_log(path: Path) -> tuple[TextIO, csv.DictWriter]:
    if path.parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    handle = path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
    if is_new:
        writer.writeheader()
    return handle, writer


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds")


def estimate_item_window(batch_start: datetime, index: int, item_ms: float) -> tuple[str, str]:
    start = batch_start + timedelta(milliseconds=item_ms * index)
    end = start + timedelta(milliseconds=item_ms)
    return iso_utc(start), iso_utc(end)


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def truth_value(item: Dict[str, Any]) -> Optional[bool]:
    for key in ("ground_truth_is_hate", "manual_is_hate", "original_is_hate", "expected_is_hate", "is_hate"):
        if key not in item:
            continue
        value = item.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "hate", "hatespeech", "offensive"}:
                return True
            if normalized in {"0", "false", "no", "n", "normal", "neutral"}:
                return False
    return None


def confusion_class(predicted: bool, truth: Optional[bool]) -> str:
    if truth is None:
        return ""
    if predicted and truth:
        return "TP"
    if not predicted and truth:
        return "FN"
    if predicted and not truth:
        return "FP"
    return "TN"


def write_run_start(writer: csv.DictWriter, run_id: str, model_label: str) -> None:
    writer.writerow(
        {
            "record_type": "RUN_START",
            "run_id": run_id,
            "model": model_label,
            "start_time_utc": iso_utc(utc_now()),
        }
    )


def write_run_summary(
    writer: csv.DictWriter,
    run_id: str,
    model_label: str,
    rows: Iterable[Dict[str, Any]],
    total_runtime_ms: float,
) -> None:
    row_list = list(rows)
    durations = [float(row["processing_time_ms"]) for row in row_list]
    chars = [int(row["char_count"]) for row in row_list]
    words = [int(row["word_count"]) for row in row_list]
    tokens = [int(row["token_count"]) for row in row_list]
    confusion = {"TP": 0, "FN": 0, "FP": 0, "TN": 0}
    for row in row_list:
        value = row.get("confusion_class", "")
        if value in confusion:
            confusion[value] += 1

    count = len(row_list)
    writer.writerow(
        {
            "record_type": "RUN_SUMMARY",
            "run_id": run_id,
            "model": model_label,
            "end_time_utc": iso_utc(utc_now()),
            "processed_items": count,
            "total_runtime_ms": f"{total_runtime_ms:.3f}",
            "min_processing_time_ms": f"{min(durations):.3f}" if durations else "",
            "max_processing_time_ms": f"{max(durations):.3f}" if durations else "",
            "avg_processing_time_ms": f"{(sum(durations) / count):.3f}" if count else "",
            "avg_char_count": f"{(sum(chars) / count):.2f}" if count else "",
            "avg_word_count": f"{(sum(words) / count):.2f}" if count else "",
            "avg_token_count": f"{(sum(tokens) / count):.2f}" if count else "",
        }
    )
    if sum(confusion.values()) > 0:
        writer.writerow(
            {
                "record_type": "CONFUSION_MATRIX",
                "run_id": run_id,
                "model": model_label,
                "tp": confusion["TP"],
                "fn": confusion["FN"],
                "fp": confusion["FP"],
                "tn": confusion["TN"],
            }
        )
