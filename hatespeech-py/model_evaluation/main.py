import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import csv
import ast
import re

ROOT_DIR = Path(__file__).resolve().parents[1]
EVALUATION_DIR = Path(__file__).resolve().parent
DATASET_DIR = EVALUATION_DIR / "dataset"
# Allow importing from hatespeech-py/src when running from model_evaluation/.
sys.path.insert(0, str(ROOT_DIR))

from src.io_utils import load_input, prepare_output, read_input_text, write_output
from src.inference import run_inference
from src.model_loader import load_model
from src.config import MODEL_CATALOG

# Built-in dataset slots used by --dataset-index.
DATASET_SLOTS = {
    1: str(DATASET_DIR / "1-SemEval2020Task12" / "extended_test" / "test_a_tweets_all.tsv"),
    2: str(DATASET_DIR / "2-Davidson" / "data" / "labeled_data.csv"),
    3: str(DATASET_DIR / "3-A-Benchmark-Dataset" / "data" / "gab.csv"),
    4: str(DATASET_DIR / "3-A-Benchmark-Dataset" / "data" / "reddit.csv"),
}
LABELS_SLOTS = {
    1: str(DATASET_DIR / "1-SemEval2020Task12" / "extended_test" / "test_a_labels_all.csv"),
    2: str(DATASET_DIR / "2-Davidson" / "data" / "labeled_data.csv"),
    3: "",
    4: "",
}

# Ground-truth values converted to binary positive labels for metric calculation.
POS_LABEL_VALUES = ["OFF"]
POS_LABEL_VALUES_BY_DATASET = {
    1: ["OFF"],
    2: ["0", "1"],
    3: ["1"],
    4: ["1"],
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="",
        help="Path to dataset TSV, CSV, or JSON.",
    )
    parser.add_argument(
        "--dataset-index",
        type=int,
        default=None,
        choices=[1, 2, 3, 4],
        help="Select dataset slot 1-4.",
    )
    parser.add_argument(
        "--models",
        default="all",
        help="Comma-separated model aliases/IDs to run, or 'all'.",
    )
    parser.add_argument(
        "--model-source",
        choices=["auto", "offline", "online"],
        default="auto",
        help="Model source. auto uses local model if it exists, otherwise online.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT_DIR / "model_evaluation" / "outputs"),
        help="Where to write model outputs.",
    )
    parser.add_argument(
        "--save-outputs",
        action="store_true",
        help="Save per-model outputs to --output-dir.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for inference.",
    )
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=128,
        help="Max sequence length.",
    )
    parser.add_argument(
        "--use-cuda",
        action="store_true",
        help="Use CUDA if available.",
    )
    parser.add_argument(
        "--label-file",
        default="",
        help="CSV with ground-truth labels (id,label).",
    )
    parser.add_argument(
        "--label-pos-values",
        default=",".join(POS_LABEL_VALUES),
        help="Comma-separated label values considered positive (hate).",
    )
    parser.add_argument(
        "--hate-threshold",
        type=float,
        default=None,
        help="Threshold over hate_score for binary/multilabel (default 0.5).",
    )
    parser.add_argument(
        "--log-file",
        default="",
        help="Optional log file path.",
    )
    return parser.parse_args()

def setup_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger("hatespeech_model_evaluation")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        if log_file:
            log_path = Path(log_file)
            if log_path.parent and not log_path.parent.exists():
                log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(str(log_path), encoding="utf-8")
            fh.setLevel(logging.INFO)
            fh.setFormatter(formatter)
            logger.addHandler(fh)
    return logger


def _load_tsv_input(path: str, logger: logging.Logger) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    # TSV loader: expects at least an id column and a text-ish column (tweet/text).
    items: List[Dict[str, Any]] = []
    text_keys = ("text", "tweet", "comment", "body", "content", "sentence")
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if not row:
                continue
            cleaned = {k: v for k, v in row.items() if k is not None}
            if "text" not in cleaned or not cleaned.get("text"):
                for key in text_keys:
                    if key in cleaned and cleaned[key]:
                        cleaned["text"] = cleaned[key]
                        break
            items.append(cleaned)
    logger.info("Parsed TSV (%d items).", len(items))
    return {"items": items}, items


def _load_dataset_1(path: str, logger: logging.Logger) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    # SemEval2020 Task 12 uses TSV in the configured slot, but keep JSON support for custom paths.
    if path.lower().endswith(".tsv"):
        return _load_tsv_input(path, logger)
    raw_text, input_source = read_input_text(path)
    logger.info("Input: %s", input_source)
    return load_input(raw_text, logger=logger)


def _load_dataset_2(path: str, logger: logging.Logger) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    # Davidson CSV uses "tweet" as text and "class" as the ground-truth label.
    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            cleaned = {k: v for k, v in row.items() if k is not None}
            item_id = (
                cleaned.get("id")
                or cleaned.get("tweet_id")
                or cleaned.get("tweetid")
                or cleaned.get("")
                or cleaned.get("Unnamed: 0")
                or cleaned.get("index")
            )
            text = cleaned.get("tweet") or cleaned.get("text") or ""
            cleaned["text"] = text
            if item_id is not None:
                cleaned["id"] = item_id
            items.append(cleaned)
    logger.info("Parsed Davidson CSV (%d items).", len(items))
    return {"items": items}, items


def _normalize_csv_row(row: Dict[str, Any]) -> Dict[str, Any]:
    # Some benchmark CSV exports contain BOM or stray delimiter characters in header names.
    normalized: Dict[str, Any] = {}
    for key, value in row.items():
        if key is None:
            continue
        clean_key = str(key).replace("\ufeff", "").replace("›", "").strip()
        normalized[clean_key] = value
    return normalized


def _parse_benchmark_indices(raw_idx: Any) -> List[int]:
    # hate_speech_idx is stored as text like "[1, 3]" or "n/a"; return post indexes.
    if raw_idx is None:
        return []
    text = str(raw_idx).strip()
    if not text or text.lower() == "n/a":
        return []
    try:
        parsed = ast.literal_eval(text)
    except Exception:
        return [int(match) for match in re.findall(r"\d+", text)]
    if isinstance(parsed, (list, tuple)):
        indices: List[int] = []
        for value in parsed:
            try:
                indices.append(int(value))
            except (TypeError, ValueError):
                continue
        return indices
    return []


def _parse_numbered_segments(raw_value: Any) -> List[str]:
    # Benchmark rows combine a full conversation into numbered id/text blocks.
    if raw_value is None:
        return []
    text = str(raw_value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    pattern = re.compile(r"(?m)^\s*(\d+)\.\s*")
    matches = list(pattern.finditer(text))
    if not matches:
        return [text]
    segments: List[str] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        segment = text[start:end].strip()
        segments.append(segment)
    return segments


def _parse_response_list(raw_value: Any) -> List[str]:
    if raw_value is None:
        return []
    text = str(raw_value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
    except Exception:
        return [text]
    if isinstance(parsed, (list, tuple)):
        return [str(value).strip() for value in parsed if str(value).strip()]
    return [str(parsed).strip()]


def _load_benchmark_conversation_csv(
    path: str,
    logger: logging.Logger,
    dataset_name: str,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    # Gab/Reddit rows are conversations. Expand them into post-level items
    # because the models classify one text item at a time.
    items: List[Dict[str, Any]] = []
    conversation_count = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_index, row in enumerate(reader, start=1):
            if not row:
                continue
            cleaned = _normalize_csv_row(row)
            message_ids = _parse_numbered_segments(cleaned.get("id"))
            message_texts = _parse_numbered_segments(cleaned.get("text"))
            hate_indices = set(_parse_benchmark_indices(cleaned.get("hate_speech_idx")))
            responses = _parse_response_list(cleaned.get("response"))
            conversation_count += 1

            segment_count = max(len(message_ids), len(message_texts))
            if segment_count == 0:
                continue

            for message_index in range(1, segment_count + 1):
                message_text = (
                    message_texts[message_index - 1]
                    if message_index - 1 < len(message_texts)
                    else ""
                )
                message_id = (
                    message_ids[message_index - 1]
                    if message_index - 1 < len(message_ids)
                    else f"{dataset_name.lower()}_{row_index}_{message_index}"
                )
                items.append(
                    {
                        "id": str(message_id).strip(),
                        "text": message_text,
                        "label": "1" if message_index in hate_indices else "0",
                        "message_index": message_index,
                        "conversation_row": row_index,
                        "conversation_size": segment_count,
                        "hate_speech_idx": sorted(hate_indices),
                        "response": responses,
                        "dataset_name": dataset_name.lower(),
                    }
                )
    logger.info(
        "Parsed %s CSV (%d conversations expanded to %d post items).",
        dataset_name,
        conversation_count,
        len(items),
    )
    return {"items": items}, items


def _load_dataset_3(path: str, logger: logging.Logger) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    return _load_benchmark_conversation_csv(path, logger, "Gab")


def _load_dataset_4(path: str, logger: logging.Logger) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    return _load_benchmark_conversation_csv(path, logger, "Reddit")

DATASET_LOADERS = {
    1: _load_dataset_1,
    2: _load_dataset_2,
    3: _load_dataset_3,
    4: _load_dataset_4,
}


def _select_models(models_arg: str) -> List[Dict[str, Any]]:
    if models_arg.strip().lower() == "all":
        return list(MODEL_CATALOG)
    wanted = {m.strip().lower() for m in models_arg.split(",") if m.strip()}
    selected = []
    for entry in MODEL_CATALOG:
        model_ids = [
            entry.get("model_id", ""),
            entry.get("online_model_id", ""),
            entry.get("offline_model_id", ""),
        ]
        if entry["alias"].lower() in wanted or any(model_id.lower() in wanted for model_id in model_ids):
            selected.append(entry)
    return selected


def _resolve_offline_model_path(model_id: str) -> str:
    path = Path(model_id)
    if path.is_absolute():
        return str(path)
    return str(ROOT_DIR / path)


def _select_model_id(entry: Dict[str, Any], model_source: str) -> str:
    online_model_id = entry.get("online_model_id") or entry.get("model_id")
    offline_model_id = entry.get("offline_model_id") or entry.get("model_id")
    if model_source == "online":
        if not online_model_id:
            raise ValueError(f"Catalog entry '{entry.get('alias', '')}' has no online_model_id.")
        return online_model_id

    if offline_model_id:
        offline_path = _resolve_offline_model_path(offline_model_id)
        if Path(offline_path).exists():
            return offline_path
        if model_source == "offline":
            raise FileNotFoundError(
                f"Offline model not found for '{entry.get('alias', '')}': {offline_path}"
            )

    if online_model_id:
        return online_model_id
    raise ValueError(f"Catalog entry '{entry.get('alias', '')}' has no usable model ID.")


def _parse_pos_label_names(value: str) -> List[str]:
    names = [n.strip().lower() for n in value.split(",") if n.strip()]
    return names or [n.lower() for n in POS_LABEL_VALUES]


def _load_label_csv(path: str, logger: logging.Logger) -> Dict[str, str]:
    # CSV with "id,label" rows or dataset-specific headers (e.g., Davidson).
    labels: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        first_line = f.readline()
        f.seek(0)
        if "class" in first_line and "tweet" in first_line:
            reader = csv.DictReader(f)
            for row in reader:
                if not row:
                    continue
                item_id = (
                    row.get("id")
                    or row.get("tweet_id")
                    or row.get("tweetid")
                    or row.get("")
                    or row.get("Unnamed: 0")
                    or row.get("index")
                )
                label_value = row.get("class")
                if item_id is None or label_value is None:
                    continue
                labels[str(item_id)] = str(label_value)
            logger.info("Loaded labels: %d (header CSV)", len(labels))
            return labels
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 2:
                continue
            first = row[0].strip()
            second = row[1].strip()
            if first.lower() in {"id", "tweet_id"} and second.lower() in {"label", "class"}:
                continue
            if not first:
                continue
            labels[first] = second
    logger.info("Loaded labels: %d", len(labels))
    return labels


def _map_labels_to_items(
    items: List[Any],
    labels_map: Dict[str, str],
    pos_values: Sequence[str],
) -> List[Optional[int]]:
    # Prefer labels loaded from a label file; fall back to labels already present on items.
    pos_set = {v.lower() for v in pos_values}
    y_true_all: List[Optional[int]] = []
    for item in items:
        label_value = None
        if isinstance(item, dict):
            item_id = item.get("id") or item.get("tweet_id") or item.get("tweetid")
            if item_id is not None:
                label_value = labels_map.get(str(item_id))
            if label_value is None:
                label_value = item.get("label") or item.get("class")
        if label_value is None:
            y_true_all.append(None)
            continue
        y_true_all.append(1 if label_value.strip().lower() in pos_set else 0)
    return y_true_all


def _compute_metrics(
    y_true: List[int],
    y_pred: List[int],
) -> Dict[str, float]:
    # Binary classification metrics.
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    total = len(y_true)
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _format_metric(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _render_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No results."
    headers = [
        "model",
        "items",
        "labeled",
        "hate_count",
        "hate_rate",
        "acc",
        "prec",
        "rec",
        "f1",
    ]
    col_widths = {h: len(h) for h in headers}
    for r in rows:
        for h in headers:
            col_widths[h] = max(col_widths[h], len(str(r.get(h, ""))))
    sep = " | "
    header_line = sep.join(h.ljust(col_widths[h]) for h in headers)
    divider = "-+-".join("-" * col_widths[h] for h in headers)
    body = "\n".join(sep.join(str(r.get(h, "")).ljust(col_widths[h]) for h in headers) for r in rows)
    return f"{header_line}\n{divider}\n{body}"

def main() -> None:
    args = parse_args()
    logger = setup_logger(args.log_file)

    if not args.input and args.dataset_index is None:
        logger.error("No dataset provided. Pass --input or --dataset-index.")
        raise SystemExit(2)

    dataset_index = args.dataset_index or 1
    input_path = args.input
    if args.dataset_index is not None:
        selected = DATASET_SLOTS.get(args.dataset_index, "")
        if not selected:
            logger.error(
                "Dataset slot %d is not configured yet. Update DATASET_SLOTS.",
                args.dataset_index,
            )
            return
        input_path = selected
        dataset_index = args.dataset_index
    loader = DATASET_LOADERS.get(dataset_index, _load_dataset_1)
    logger.info("Input: %s (dataset %d)", input_path, dataset_index)
    original_data, items = loader(input_path, logger)
    if not items:
        logger.info("No items to process.")
        return

    selected_models = _select_models(args.models)
    if not selected_models:
        logger.error("No models selected. Check --models argument.")
        return

    # Load ground-truth labels for metrics (optional but recommended).
    labels_path = args.label_file
    if args.dataset_index is not None and not labels_path:
        labels_path = LABELS_SLOTS.get(args.dataset_index, "")
    labels_map: Dict[str, str] = {}
    if labels_path:
        labels_path_obj = Path(labels_path)
        if labels_path_obj.exists():
            labels_map = _load_label_csv(str(labels_path_obj), logger)
        else:
            logger.warning("Label file not found: %s", labels_path)

    default_pos_arg = ",".join(POS_LABEL_VALUES)
    if (
        args.label_pos_values == default_pos_arg
        and dataset_index in POS_LABEL_VALUES_BY_DATASET
        and POS_LABEL_VALUES_BY_DATASET[dataset_index]
    ):
        pos_values = POS_LABEL_VALUES_BY_DATASET[dataset_index]
    else:
        pos_values = _parse_pos_label_names(args.label_pos_values)
    y_true_all = _map_labels_to_items(items, labels_map, pos_values)
    labeled_indices = [i for i, y in enumerate(y_true_all) if y is not None]
    y_true = [y_true_all[i] for i in labeled_indices if y_true_all[i] is not None]
    y_true_positive = sum(1 for y in y_true if y == 1)
    y_true_negative = sum(1 for y in y_true if y == 0)
    y_true_unlabeled = len(y_true_all) - len(labeled_indices)
    logger.info(
        "Ground truth stats: labeled=%d positive=%d negative=%d unlabeled=%d pos_values=%s",
        len(y_true),
        y_true_positive,
        y_true_negative,
        y_true_unlabeled,
        ",".join(pos_values),
    )

    # Prepare output folder only when saving is requested.
    output_dir = Path(args.output_dir)
    if args.save_outputs:
        output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: List[Dict[str, Any]] = []
    for entry in selected_models:
        alias = entry["alias"]
        model_id = _select_model_id(entry, args.model_source)
        model_type = entry["model_type"]
        hate_label_names = entry.get("hate_label_names", [])
        hate_label_ids = entry.get("hate_label_ids", [])

        logger.info("=== Running model: %s (%s) ===", alias, model_id)
        model = load_model(
            model_id=model_id,
            model_type=model_type,
            use_cuda=args.use_cuda,
            batch_size=args.batch_size,
            max_seq_length=args.max_seq_length,
            logger=logger,
        )
        logger.info(
            "Model config: problem_type=%s, num_labels=%s, id2label=%s",
            getattr(model.model.config, "problem_type", None),
            getattr(model.model.config, "num_labels", None),
            getattr(model.model.config, "id2label", None),
        )
        output_items, hate_ids = run_inference(
            model=model,
            items=items,
            hate_label_ids=hate_label_ids,
            hate_label_names=hate_label_names,
            hate_threshold=args.hate_threshold,
            log_items=False,
            log_texts=False,
            logger=logger,
        )
        logger.info("Hate label IDs: %s", hate_ids)

        output_data = prepare_output(original_data, output_items)
        out_path = output_dir / f"{alias}.json"
        if args.save_outputs:
            write_output(str(out_path), output_data)
            logger.info("Saved output: %s", out_path)

        y_pred = [1 if item.get("is_hate_speech") else 0 for item in output_items]
        labeled = len(y_true)
        metrics: Dict[str, float] = {}
        if labeled:
            y_pred_labeled = [y_pred[i] for i in labeled_indices]
            metrics = _compute_metrics(y_true, y_pred_labeled)
        hate_rate = sum(y_pred) / len(y_pred) if y_pred else 0.0
        hate_count = sum(y_pred)
        summary_rows.append(
            {
                "model": alias,
                "items": str(len(items)),
                "labeled": str(labeled),
                "hate_count": str(hate_count),
                "hate_rate": f"{hate_rate:.4f}",
                "acc": _format_metric(metrics.get("accuracy") if labeled else None),
                "prec": _format_metric(metrics.get("precision") if labeled else None),
                "rec": _format_metric(metrics.get("recall") if labeled else None),
                "f1": _format_metric(metrics.get("f1") if labeled else None),
            }
        )

    logger.info("=== Summary ===")
    print(_render_table(summary_rows))


if __name__ == "__main__":
    main()
