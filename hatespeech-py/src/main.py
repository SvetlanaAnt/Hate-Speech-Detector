import argparse
import json
import logging
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    ALLOWED_MODEL_TYPES,
    DEFAULT_BATCH_SIZE,
    DEFAULT_LOG_FILE,
    DEFAULT_MAX_SEQ_LENGTH,
    MODEL_CATALOG,
)
from .download_models import DEFAULT_MODELS_DIR, download_models
from .evaluation_logging import open_evaluation_log, resolve_evaluation_log_path, write_run_start
from .inference import run_inference
from .io_utils import (
    extract_text,
    load_input,
    prepare_output,
    read_input_text,
    write_output,
)
from .logging_utils import get_package_versions, setup_logging
from .model_loader import load_model

ROOT_DIR = Path(__file__).resolve().parents[1]

# Parse CLI arguments and return the populated namespace.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    required_group = parser.add_argument_group("Required")
    model_group = required_group.add_mutually_exclusive_group(required=True)
    model_group.add_argument(
        "--model",
        help="Model alias from catalog",
    )
    model_group.add_argument(
        "--models",
        help="Comma-separated model aliases. If set, overrides --model.",
    )
    model_group.add_argument(
        "--list-models",
        action="store_true",
        help="Print catalog models and exit.",
    )
    model_group.add_argument(
        "--audit-models",
        action="store_true",
        help="Load all catalog models and print id2label.",
    )
    model_group.add_argument(
        "--download-models",
        nargs="?",
        const="all",
        help="Download catalog models locally. Use without value for all, or pass comma-separated aliases/IDs.",
    )
    optional_group = parser.add_argument_group("Optional")
    optional_group.add_argument(
        "--input",
        default="",
        help="Path to JSON file. If omitted, reads from stdin.",
    )
    optional_group.add_argument(
        "--output",
        default="",
        help="Path to JSON file. If omitted, writes to stdout.",
    )
    optional_group.add_argument(
        "--hate-label-id",
        type=int,
        action="append",
        default=[],
        help="Label ID representing hate speech (can be repeated).",
    )
    optional_group.add_argument(
        "--hate-label-name",
        action="append",
        default=[],
        help="Label name representing hate speech (can be repeated).",
    )
    optional_group.add_argument(
        "--hate-threshold",
        type=float,
        default=0.5,
        help="Threshold on hate_score for binary/multilabel (default 0.5).",
    )
    optional_group.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Batch size for inference.",
    )
    optional_group.add_argument(
        "--max-seq-length",
        type=int,
        default=DEFAULT_MAX_SEQ_LENGTH,
        help="Maximum sequence length.",
    )
    optional_group.add_argument(
        "--use-cuda",
        action="store_true",
        help="Enable GPU if available.",
    )
    optional_group.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help="Path to log file.",
    )
    optional_group.add_argument(
        "--evaluation-log-file",
        default="",
        help="Path to CSV evaluation log. Defaults to evaluation_<timestamp>.csv next to timestamped --log-file.",
    )
    optional_group.add_argument(
        "--log-items",
        action="store_true",
        help="Log results for each item (without text).",
    )
    optional_group.add_argument(
        "--log-texts",
        action="store_true",
        help="Log full text of each item (WARNING: sensitive content).",
    )
    optional_group.add_argument(
        "--model-catalog",
        metavar="FILE",
        default="",
        help="Path to JSON catalog. If set, it is merged with the built-in catalog (external overrides the same alias).",
    )
    optional_group.add_argument(
        "--download-dir",
        default=str(DEFAULT_MODELS_DIR),
        help="Directory where --download-models stores local model folders.",
    )
    optional_group.add_argument(
        "--models-dir",
        default=str(DEFAULT_MODELS_DIR),
        help="Directory containing local model folders for offline/auto model loading.",
    )
    optional_group.add_argument(
        "--model-source",
        choices=["auto", "offline", "online"],
        default="auto",
        help="Model source. auto uses local model if it exists, otherwise online.",
    )
    optional_group.add_argument(
        "--predictions",
        action="store_true",
        help="If set and multiple models are used, group outputs under a predictions field per input item.",
    )
    return parser.parse_args()


# Load a JSON model catalog from disk and validate entries.
def _load_model_catalog(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Model catalog JSON must be a list.")
    allowed_model_types = ALLOWED_MODEL_TYPES
    catalog: list[dict] = []
    for idx, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"Model catalog entry {idx} must be an object.")
        if not (
            entry.get("model_id")
            or entry.get("online_model_id")
            or entry.get("offline_model_id")
        ):
            raise ValueError(
                f"Model catalog entry {idx} missing model_id/online_model_id/offline_model_id."
            )
        if "model_type" in entry and entry["model_type"] is not None:
            model_type = entry["model_type"]
            if not isinstance(model_type, str):
                raise ValueError(
                    f"Model catalog entry {idx} model_type must be a string or null."
                )
            normalized = model_type.strip().lower()
            if normalized and normalized not in allowed_model_types:
                raise ValueError(
                    "Model catalog entry "
                    f"{idx} has unsupported model_type '{model_type}'. "
                    f"Allowed: {', '.join(sorted(allowed_model_types))}."
                )
            entry["model_type"] = normalized
        catalog.append(entry)
    return catalog


# Merge external catalog entries into the base catalog by alias. External overrides by alias.
def _merge_model_catalogs(base: list[dict], external: list[dict]) -> list[dict]:
    merged = list(base)
    alias_to_index = {
        entry.get("alias"): idx for idx, entry in enumerate(merged) if entry.get("alias")
    }
    for entry in external:
        alias = entry.get("alias")
        if alias and alias in alias_to_index:
            merged[alias_to_index[alias]] = entry
        else:
            merged.append(entry)
            if alias:
                alias_to_index[alias] = len(merged) - 1
    return merged

# Clean a value for stable table output in the CLI. Remove newlines and table separators for clean CLI output.
def _sanitize_table_value(value: str) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace(" | ", " ")


# Print the model catalog as a simple table.
def _print_model_catalog(catalog: list[dict]) -> None:
    headers = ["alias", "model_type", "offline_model_id", "online_model_id", "description"]
    rows = [
        [
            _sanitize_table_value(entry.get("alias", "")),
            _sanitize_table_value(entry.get("model_type", "")),
            _sanitize_table_value(entry.get("offline_model_id", entry.get("model_id", ""))),
            _sanitize_table_value(entry.get("online_model_id", entry.get("model_id", ""))),
            _sanitize_table_value(entry.get("description", "")),
        ]
        for entry in catalog
    ]
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, value in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(value)))
    sep = " | "
    header_line = sep.join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    divider = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_line)
    print(divider)
    for row in rows:
        print(sep.join(str(row[i]).ljust(col_widths[i]) for i in range(len(headers))))

# Load each catalog model and print its id2label mapping.
def _audit_model_catalog(
    catalog: list[dict],
    model_source: str,
    use_cuda: bool,
    batch_size: int,
    max_seq_length: int,
    logger: logging.Logger,
) -> None:
    headers = ["alias", "model_source", "model_id", "model_type", "id2label"]
    rows = []
    for entry in catalog:
        alias = entry.get("alias", "")
        model_type = entry.get("model_type", "")
        try:
            model_id = _select_model_id(entry, model_source)
            model = load_model(
                model_id=model_id,
                model_type=model_type,
                use_cuda=use_cuda,
                batch_size=batch_size,
                max_seq_length=max_seq_length,
                logger=logger,
            )
            id2label = getattr(model.model.config, "id2label", None)
        except Exception as exc:
            model_id = ""
            id2label = f"ERROR: {exc}"
        rows.append([alias, model_source, model_id, model_type, str(id2label)])

    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, value in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(value)))
    sep = " | "
    header_line = sep.join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    divider = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_line)
    print(divider)
    for row in rows:
        print(sep.join(str(row[i]).ljust(col_widths[i]) for i in range(len(headers))))

# Normalize --models/--model into a list of model keys (list of aliases or model IDs)
def _parse_models_arg(models_arg: str, model_arg: str, catalog: list[dict]) -> list[str]:
    raw = models_arg.strip() if models_arg else ""
    if not raw and model_arg:
        raw = model_arg.strip()
    if raw.lower() == "all":
        return [entry.get("alias", "") for entry in catalog if entry.get("alias")]
    return [m.strip() for m in raw.split(",") if m.strip()]

# Find a catalog entry by alias or any model ID (case-insensitive).
def _find_model_entry(model_key: str, catalog: list[dict]) -> dict | None:
    key = model_key.strip().lower()
    for entry in catalog:
        if entry.get("alias", "").lower() == key:
            return entry
        for field in ("model_id", "online_model_id", "offline_model_id"):
            if entry.get(field, "").lower() == key:
                return entry
    return None


def _resolve_offline_model_path(model_id: str, models_dir: str) -> str:
    path = Path(model_id)
    if path.is_absolute():
        return str(path)
    parts = path.parts
    if parts and parts[0] == "models":
        return str(Path(models_dir) / Path(*parts[1:]))
    return str(ROOT_DIR / path)


def _select_model_id(entry: dict, model_source: str, models_dir: str = str(DEFAULT_MODELS_DIR)) -> str:
    online_model_id = entry.get("online_model_id") or entry.get("model_id")
    offline_model_id = entry.get("offline_model_id") or entry.get("model_id")
    if model_source == "online":
        if not online_model_id:
            raise ValueError(f"Catalog entry '{entry.get('alias', '')}' has no online_model_id.")
        return online_model_id

    if offline_model_id:
        offline_path = _resolve_offline_model_path(offline_model_id, models_dir)
        if Path(offline_path).exists():
            return offline_path
        if model_source == "offline":
            raise FileNotFoundError(
                f"Offline model not found for '{entry.get('alias', '')}': {offline_path}"
            )

    if online_model_id:
        return online_model_id
    raise ValueError(f"Catalog entry '{entry.get('alias', '')}' has no usable model ID.")

# Run the CLI workflow end-to-end.
# parse args, load models, run inference, and emit JSON.
def main() -> None:
    args = parse_args()
    logger = setup_logging(args.log_file)

    try:
        catalog = MODEL_CATALOG
        if args.model_catalog:
            external_catalog = _load_model_catalog(args.model_catalog)
            catalog = _merge_model_catalogs(MODEL_CATALOG, external_catalog)
        if args.list_models:
            _print_model_catalog(catalog)
            return
        if args.audit_models:
            _audit_model_catalog(
                catalog=catalog,
                model_source=args.model_source,
                use_cuda=args.use_cuda,
                batch_size=args.batch_size,
                max_seq_length=args.max_seq_length,
                logger=logger,
            )
            return
        if args.download_models:
            model_names = None
            if args.download_models.strip().lower() != "all":
                model_names = [
                    name.strip()
                    for name in args.download_models.split(",")
                    if name.strip()
                ]
            download_models(model_names=model_names, output_dir=args.download_dir)
            return

        logger.info("=== HateSpeech run started ===")
        logger.info("Timestamp: %s", datetime.now(timezone.utc).isoformat())
        logger.info("Python: %s", sys.version.replace("\n", " "))
        logger.info("Platform: %s", platform.platform())
        logger.info("Args: %s", vars(args))
        logger.info("Package versions: %s", get_package_versions())
        evaluation_path = resolve_evaluation_log_path(args.log_file, args.evaluation_log_file)
        evaluation_handle, evaluation_writer = open_evaluation_log(evaluation_path)
        logger.info("Evaluation log file: %s", evaluation_path)

        try:
            # Read input text from stdin or a file path.
            raw_text, input_source = read_input_text(args.input)
            logger.info("Input: %s", input_source)

            # Parse input JSON into items while keeping the original structure.
            original_data, items = load_input(raw_text, logger=logger)
            logger.info("Items count: %d", len(items))

            if not items:
                output_data = prepare_output(original_data, [])
                write_output(args.output, output_data, logger=logger, is_empty=True)
                logger.info("=== HateSpeech run finished (empty input) ===")
                return

            # Normalize requested model(s) to a list of aliases/IDs.
            model_keys = _parse_models_arg(args.models, args.model, catalog)
            if not model_keys:
                raise ValueError("No model alias/ID provided. Use --model or --models.")

            group_predictions = args.predictions and len(model_keys) > 1
            combined_items = []
            # Pre-build multi-model output structure if needed.
            if group_predictions:
                texts = [extract_text(item) for item in items]
                for i, item in enumerate(items):
                    base_item = dict(item) if isinstance(item, dict) else {"text": texts[i]}
                    base_item["predictions"] = {}
                    combined_items.append(base_item)

            for model_key in model_keys:
                # Resolve catalog entry and default hate labels.
                model_entry = _find_model_entry(model_key, catalog)
                if not model_entry:
                    raise ValueError(
                        "Unknown model alias: "
                        f"{model_key}. Use --list-models or add it to MODEL_CATALOG/--model-catalog."
                    )
                model_id = _select_model_id(model_entry, args.model_source, args.models_dir)
                model_type = model_entry.get("model_type")
                hate_label_ids = args.hate_label_id
                hate_label_names = args.hate_label_name
                if model_entry:
                    if not hate_label_ids and model_entry.get("hate_label_ids"):
                        hate_label_ids = list(model_entry["hate_label_ids"])
                    if not hate_label_names and model_entry.get("hate_label_names"):
                        hate_label_names = list(model_entry["hate_label_names"])

                # Load the model and execute inference.
                model_run_started = time.perf_counter()
                model = load_model(
                    model_id=model_id,
                    model_type=model_type,
                    use_cuda=args.use_cuda,
                    batch_size=args.batch_size,
                    max_seq_length=args.max_seq_length,
                    logger=logger,
                )
                logger.info("Model loaded: %s", model_id)
                logger.info(
                    "Model config: num_labels=%s, id2label=%s",
                    getattr(model.model.config, "num_labels", None),
                    getattr(model.model.config, "id2label", None),
                )
                model_label = model_entry.get("alias") if model_entry else model_key
                run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                write_run_start(evaluation_writer, run_id, model_label)
                output_items, hate_ids = run_inference(
                    model=model,
                    items=items,
                    hate_label_ids=hate_label_ids,
                    hate_label_names=hate_label_names,
                    hate_threshold=args.hate_threshold,
                    log_items=args.log_items,
                    log_texts=args.log_texts,
                    logger=logger,
                    evaluation_writer=evaluation_writer,
                    evaluation_run_id=run_id,
                    evaluation_model_label=model_label,
                    evaluation_total_started=model_run_started,
                )
                logger.info("Hate label IDs: %s", hate_ids)

                if not group_predictions:
                    if len(model_keys) == 1:
                        combined_items = output_items
                    else:
                        for out_item in output_items:
                            out_item["model"] = model_label
                        combined_items.extend(output_items)
                else:
                    alias = model_entry.get("alias") if model_entry else model_key
                    for i, out_item in enumerate(output_items):
                        pred = {
                            "label_id": out_item.get("label_id"),
                            "label_name": out_item.get("label_name"),
                            "is_hate_speech": out_item.get("is_hate_speech"),
                        }
                        if "hate_score" in out_item:
                            pred["hate_score"] = out_item.get("hate_score")
                        combined_items[i]["predictions"][alias] = pred

            output_data = prepare_output(original_data, combined_items)
            write_output(args.output, output_data, logger=logger)
            logger.info("=== HateSpeech run finished ===")
        finally:
            evaluation_handle.close()
    except Exception as exc:
        logger.exception("Run failed with exception: %s", exc)
        raise


if __name__ == "__main__":
    main()
