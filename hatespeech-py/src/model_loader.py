import logging
from dataclasses import dataclass
from typing import Optional, Any

import torch
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

# Infer a model type from the model ID when not explicitly provided.
# Priority: explicit model_type unless "auto"; otherwise infer from model_id; error if unknown.
def _resolve_model_type(model_id: str, model_type: Optional[str]) -> str:
    if model_type and model_type != "auto":
        return model_type
    model_id_lower = model_id.lower()
    if "roberta" in model_id_lower:
        return "roberta"
    if "electra" in model_id_lower:
        return "electra"
    if "bertweet" in model_id_lower:
        return "bertweet"
    if "bert" in model_id_lower:
        return "bert"
    try:
        config = AutoConfig.from_pretrained(model_id)
        config_type = getattr(config, "model_type", None)
        if isinstance(config_type, str):
            normalized = config_type.lower()
            if normalized == "xlm-roberta":
                normalized = "roberta"
            if normalized in {"bert", "roberta", "electra", "bertweet"}:
                return normalized
    except Exception:
        pass
    raise ValueError(
        "Model type not provided or not recognized for model_id="
        f"'{model_id}' (model_type={model_type}); pass --model-type "
        "(e.g. electra, roberta)."
    )

@dataclass
class LoadedModel:
    model: Any
    tokenizer: Any
    device: torch.device
    batch_size: int
    max_seq_length: int
    model_id: str
    model_type: str


# Load a Hugging Face sequence classification model with its tokenizer.
def load_model(
    model_id: str,
    model_type: Optional[str],
    use_cuda: bool,
    batch_size: int,
    max_seq_length: int,
    logger: Optional[logging.Logger] = None,
) -> LoadedModel:
    resolved_model_type = _resolve_model_type(model_id, model_type)
    if logger:
        device = "cuda" if use_cuda and torch.cuda.is_available() else "cpu"
        logger.info(
            "Loading model: %s (type=%s, device=%s, batch_size=%d, max_seq_length=%d)",
            model_id,
            resolved_model_type,
            device,
            batch_size,
            max_seq_length,
        )
    device = torch.device("cuda" if use_cuda and torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_id, attn_implementation="eager"
    )
    model.to(device)
    model.eval()
    if logger:
        logger.info("Model initialization completed.")
    return LoadedModel(
        model=model,
        tokenizer=tokenizer,
        device=device,
        batch_size=batch_size,
        max_seq_length=max_seq_length,
        model_id=model_id,
        model_type=resolved_model_type,
    )
