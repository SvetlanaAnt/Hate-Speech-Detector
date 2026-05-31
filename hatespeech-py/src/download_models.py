
import argparse
from pathlib import Path
from typing import Iterable

from .config import MODEL_CATALOG

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODELS_DIR = ROOT_DIR / "models"


def _selected_catalog_entries(model_names: Iterable[str] | None) -> list[dict]:
    if not model_names:
        return list(MODEL_CATALOG)

    wanted = {name.strip().lower() for name in model_names if name.strip()}
    selected = []
    for entry in MODEL_CATALOG:
        alias = entry.get("alias", "").lower()
        online_model_id = entry.get("online_model_id", entry.get("model_id", "")).lower()
        offline_model_id = entry.get("offline_model_id", "").lower()
        if alias in wanted or online_model_id in wanted or offline_model_id in wanted:
            selected.append(entry)
    return selected


def download_models(
    model_names: Iterable[str] | None = None,
    output_dir: str | Path = DEFAULT_MODELS_DIR,
) -> None:
    """Download selected catalog models and save them under output_dir/alias."""
    selected_entries = _selected_catalog_entries(model_names)
    if not selected_entries:
        raise ValueError("No models selected for download.")

    base_output_dir = Path(output_dir)
    if not base_output_dir.is_absolute():
        base_output_dir = ROOT_DIR / base_output_dir
    base_output_dir.mkdir(parents=True, exist_ok=True)

    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    for entry in selected_entries:
        alias = entry["alias"]
        hf_model_id = entry.get("online_model_id") or entry.get("model_id")
        if not hf_model_id:
            raise ValueError(f"Catalog entry '{alias}' does not define online_model_id.")
        target_dir = base_output_dir / alias

        print(f"Downloading {hf_model_id} -> {target_dir}")
        tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
        model = AutoModelForSequenceClassification.from_pretrained(hf_model_id)

        tokenizer.save_pretrained(target_dir)
        model.save_pretrained(target_dir)

    print("All selected models downloaded.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "models",
        nargs="?",
        default="all",
        help="Comma-separated model aliases/IDs to download, or 'all'.",
    )
    parser.add_argument(
        "--download-dir",
        default=str(DEFAULT_MODELS_DIR),
        help="Directory where local model folders are stored.",
    )
    args = parser.parse_args()
    model_names = None
    if args.models.strip().lower() != "all":
        model_names = [name.strip() for name in args.models.split(",") if name.strip()]
    download_models(model_names=model_names, output_dir=args.download_dir)


if __name__ == "__main__":
    main()
