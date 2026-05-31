import logging
from pathlib import Path
from typing import Dict, Optional

from .config import DEFAULT_LOG_FILE

# Create (or reuse) a file logger configured for CLI usage. 
# if not added, use or create a default log file
# if it is not found either, log to stderr
def setup_logging(log_file: Optional[str]) -> logging.Logger:
    logger = logging.getLogger("hatespeech")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        log_path_value = (log_file or "").strip() or DEFAULT_LOG_FILE
        log_path = Path(log_path_value)
        try:
            if log_path.parent and not log_path.parent.exists():
                log_path.parent.mkdir(parents=True, exist_ok=True)
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            fh = logging.FileHandler(str(log_path), encoding="utf-8")
            fh.setLevel(logging.INFO)
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except Exception as exc:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.error(
                "Failed to open log file %s; logging to stderr. Error: %s",
                log_path_value,
                exc,
            )

    return logger

# Return versions for core ML dependencies when available.
def get_package_versions() -> Dict[str, str]:
    versions: Dict[str, str] = {}
    try:
        from importlib import metadata as importlib_metadata
    except Exception:
        importlib_metadata = None  # type: ignore

    if importlib_metadata is None:
        return versions

    for name in ["simpletransformers", "transformers", "torch", "numpy"]:
        try:
            versions[name] = importlib_metadata.version(name)
        except Exception:
            continue
    return versions
