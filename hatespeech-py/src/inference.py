import logging
import os
import re
import time
import unicodedata
from csv import DictWriter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch

from .config import DEFAULT_LABEL_HATE, DEFAULT_LABEL_NORMAL
from .evaluation_logging import (
    confusion_class,
    count_words,
    estimate_item_window,
    iso_utc,
    truth_value,
    utc_now,
)
from .io_utils import extract_text
from .model_loader import LoadedModel

os.environ["WANDB_DISABLED"] = "true"


def _normalize_id2label(config: Any) -> Dict[int, str]:
    id2label = getattr(config, "id2label", None) or {}
    if isinstance(id2label, list):
        id2label = {i: v for i, v in enumerate(id2label)}
    id2label_norm: Dict[int, str] = {}
    for k, v in id2label.items():
        try:
            id2label_norm[int(k)] = str(v)
        except (TypeError, ValueError):
            continue
    return id2label_norm


def _norm_label(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", label.lower())
    return " ".join(normalized.split())


_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", flags=re.IGNORECASE)
_MENTION_RE = re.compile(r"@\w+")


def _normalize_text_common(text: str) -> str:
    if not text:
        return ""
    x = unicodedata.normalize("NFKC", text)
    x = "".join(ch for ch in x if not unicodedata.category(ch).startswith("C"))
    return " ".join(x.split())


def _normalize_twitter_placeholders(text: str) -> str:
    x = _URL_RE.sub(" http ", text)
    x = _MENTION_RE.sub(" @user ", x)
    return " ".join(x.split())


def _preprocess_text_for_model(text: str, model_id: str) -> str:
    x = _normalize_text_common(text)
    model_id_lower = model_id.lower()
    model_name = Path(model_id_lower).name

    if model_id_lower == "cardiffnlp/twitter-roberta-base-hate-latest" or model_name == "roberta_twitter_hate_latest":
        x = _normalize_twitter_placeholders(x)

    if model_id_lower in {
        "tehrannlp-org/electra-base-hatexplain",
        "hate-speech-cnerg/bert-base-uncased-hatexplain",
    } or model_name in {"electra_hatexplain", "bert_hatexplain_cnerg"}:
        x = x.lower()

    return x


def _detect_label_roles(id2label: Dict[int, str]) -> Dict[str, List[int]]:
    roles = {"hate": [], "offensive": [], "normal": []}
    for idx, raw_label in id2label.items():
        label = _norm_label(str(raw_label))
        if not label:
            continue
        if (
            "normal" in label
            or "neutral" in label
            or "not hate" in label
            or "nothate" in label
            or "non hate" in label
            or "nonhate" in label
            or label == "not offensive"
        ):
            roles["normal"].append(idx)
            continue
        if "offensive" in label or "offense" in label or "abusive" in label:
            roles["offensive"].append(idx)
            continue
        if "hate" in label or "hatespeech" in label or "hate speech" in label:
            roles["hate"].append(idx)
            continue
    return roles


def _infer_problem_family(config: Any, id2label: Dict[int, str]) -> str:
    problem_type = getattr(config, "problem_type", None)
    num_labels = getattr(config, "num_labels", None)

    if problem_type == "multi_label_classification":
        return "multilabel"
    if problem_type == "single_label_classification":
        if num_labels == 2:
            return "binary_single_label"
        if isinstance(num_labels, int) and num_labels > 2:
            return "multiclass_single_label"

    if num_labels == 2:
        return "binary_single_label"
    if isinstance(num_labels, int) and num_labels > 2:
        return "multiclass_single_label"

    if id2label:
        if len(id2label) == 2:
            return "binary_single_label"
        if len(id2label) > 2:
            return "multiclass_single_label"
    return "unknown"


def _resolve_positive_label_ids(
    id2label: Dict[int, str],
    hate_label_ids: List[int],
    hate_label_names: List[str],
    num_labels: Optional[int],
    logger: logging.Logger,
) -> List[int]:
    def _normalize_label(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", name.lower())

    resolved = set(int(i) for i in hate_label_ids or [])
    has_explicit_ids = bool(hate_label_ids)

    if hate_label_names:
        target = {n.lower() for n in hate_label_names}
        target_norm = {_normalize_label(n) for n in hate_label_names}
        for idx, name in id2label.items():
            lname = str(name).lower()
            if lname in target or _normalize_label(lname) in target_norm:
                resolved.add(idx)

    if not has_explicit_ids:
        roles = _detect_label_roles(id2label)
        for key in ("hate", "offensive"):
            resolved.update(roles[key])

    if not resolved:
        if num_labels == 2:
            resolved.add(1)
            logger.warning(
                "Hate label not found; falling back to label_id=1 (binary model)."
            )
        else:
            logger.warning(
                "Unable to resolve hate label automatically. "
                "Provide --hate-label-id or --hate-label-name."
            )

    return sorted(resolved)


def _safe_prob_sum(row: torch.Tensor, indices: List[int]) -> float:
    if not indices:
        return 0.0
    values = []
    for idx in indices:
        if 0 <= idx < row.shape[0]:
            values.append(float(row[idx].detach().cpu()))
    return float(sum(values)) if values else 0.0


def _safe_prob_max(row: torch.Tensor, indices: List[int]) -> float:
    if not indices:
        return 0.0
    values = []
    for idx in indices:
        if 0 <= idx < row.shape[0]:
            values.append(float(row[idx].detach().cpu()))
    return float(max(values)) if values else 0.0


def run_inference(
    model: LoadedModel,
    items: List[Any],
    hate_label_ids: List[int],
    hate_label_names: List[str],
    hate_threshold: Optional[float],
    log_items: bool,
    log_texts: bool,
    logger: logging.Logger,
    evaluation_writer: Optional[DictWriter] = None,
    evaluation_run_id: str = "",
    evaluation_model_label: str = "",
    evaluation_total_started: Optional[float] = None,
) -> Tuple[List[Dict[str, Any]], List[int]]:
    logger.info("Running inference on %d items.", len(items))
    raw_texts = [extract_text(item) for item in items]
    clean_texts = [_preprocess_text_for_model(text, model.model_id) for text in raw_texts]

    config = model.model.config
    id2label = _normalize_id2label(config)
    num_labels = getattr(config, "num_labels", None)
    problem_family = _infer_problem_family(config, id2label)
    positive_ids = _resolve_positive_label_ids(
        id2label=id2label,
        hate_label_ids=hate_label_ids,
        hate_label_names=hate_label_names,
        num_labels=num_labels,
        logger=logger,
    )
    positive_ids_set = set(positive_ids)

    threshold = 0.5 if hate_threshold is None else float(hate_threshold)
    batch_size = getattr(model, "batch_size", None) or 32
    max_seq_length = getattr(model, "max_seq_length", None) or 512

    output_items: List[Dict[str, Any]] = []
    evaluation_rows: List[Dict[str, Any]] = []
    inference_started = time.perf_counter()

    for start in range(0, len(clean_texts), batch_size):
        batch_texts = clean_texts[start : start + batch_size]
        batch_started_at = utc_now()
        batch_started = time.perf_counter()
        inputs = model.tokenizer(
            batch_texts,
            truncation=True,
            padding=True,
            max_length=max_seq_length,
            return_tensors="pt",
        )
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.model(**inputs)
        logits = outputs.logits

        if problem_family == "multilabel":
            probs = torch.sigmoid(logits)
        else:
            probs = torch.softmax(logits, dim=1)
        batch_elapsed_ms = (time.perf_counter() - batch_started) * 1000.0
        item_elapsed_ms = batch_elapsed_ms / len(batch_texts) if batch_texts else 0.0
        batch_ended_at = utc_now()
        token_counts = [
            int(inputs["attention_mask"][i].sum().detach().cpu())
            if "attention_mask" in inputs
            else 0
            for i in range(len(batch_texts))
        ]

        for i, item in enumerate(items[start : start + batch_size]):
            raw_text = raw_texts[start + i]
            clean_text = batch_texts[i]
            if isinstance(item, dict):
                out_item = dict(item)
                out_item["clean_text"] = clean_text
            else:
                out_item = {"text": raw_text, "clean_text": clean_text}
            row = probs[i]
            top_idx = int(torch.argmax(row).detach().cpu())

            if problem_family == "multilabel":
                hate_score = _safe_prob_max(row, positive_ids)
                is_hate = hate_score >= threshold if positive_ids else False
            elif problem_family == "binary_single_label":
                hate_score = _safe_prob_max(row, positive_ids)
                is_hate = hate_score >= threshold if positive_ids else False
            else:
                hate_score = _safe_prob_sum(row, positive_ids)
                is_hate = top_idx in positive_ids_set if positive_ids else False

            out_item["label_id"] = 1 if is_hate else 0
            out_item["label_name"] = DEFAULT_LABEL_HATE if is_hate else DEFAULT_LABEL_NORMAL
            out_item["is_hate_speech"] = is_hate
            if positive_ids:
                out_item["hate_score"] = float(hate_score)
            out_item["model_label_id"] = top_idx
            if id2label:
                out_item["model_label_name"] = id2label.get(top_idx, str(top_idx))

            output_items.append(out_item)
            if evaluation_writer is not None:
                truth = truth_value(out_item)
                predicted = bool(out_item.get("is_hate_speech"))
                item_start, item_end = estimate_item_window(batch_started_at, i, item_elapsed_ms)
                evaluation_row = {
                    "record_type": "ITEM",
                    "run_id": evaluation_run_id,
                    "model": evaluation_model_label,
                    "item_id": out_item.get("id", ""),
                    "artifact_id": out_item.get("id_artifact", ""),
                    "message_type": out_item.get("message_type", ""),
                    "start_time_utc": item_start,
                    "end_time_utc": item_end,
                    "processing_time_ms": f"{item_elapsed_ms:.3f}",
                    "batch_start_time_utc": iso_utc(batch_started_at),
                    "batch_end_time_utc": iso_utc(batch_ended_at),
                    "batch_processing_time_ms": f"{batch_elapsed_ms:.3f}",
                    "char_count": len(raw_text),
                    "word_count": count_words(raw_text),
                    "token_count": token_counts[i],
                    "predicted_is_hate": predicted,
                    "hate_score": f"{float(out_item.get('hate_score', 0.0)):.6f}",
                    "label_name": out_item.get("label_name", ""),
                    "ground_truth_is_hate": "" if truth is None else truth,
                    "manual_is_hate": "",
                    "confusion_class": confusion_class(predicted, truth),
                    "text": raw_text if log_texts else "",
                }
                evaluation_writer.writerow(evaluation_row)
                evaluation_rows.append(evaluation_row)

            if log_items:
                msg_id = out_item.get("id_artifact", None)
                item_id = out_item.get("id", None)
                log_msg = (
                    f"item_id={item_id} msg_id={msg_id} "
                    f"label_id={out_item['label_id']} "
                    f"is_hate_speech={out_item['is_hate_speech']}"
                )
                if "hate_score" in out_item:
                    log_msg += f" hate_score={out_item['hate_score']:.4f}"
                logger.info(log_msg)
                if log_texts:
                    logger.info("text=%s", raw_text)

    hate_count = sum(1 for out_item in output_items if out_item.get("is_hate_speech"))
    logger.info(
        "Inference completed: %d/%d items flagged as hate speech.",
        hate_count,
        len(output_items),
    )
    if evaluation_writer is not None:
        from .evaluation_logging import write_run_summary

        write_run_summary(
            evaluation_writer,
            evaluation_run_id,
            evaluation_model_label,
            evaluation_rows,
            (time.perf_counter() - (evaluation_total_started or inference_started)) * 1000.0,
        )
    return output_items, positive_ids
