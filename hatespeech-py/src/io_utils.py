import json
import logging
import sys
from typing import Any, List, Tuple, Optional

# Read input text from a file path or stdin, returning (text, source).
def read_input_text(input_path: str) -> Tuple[str, str]:
    if input_path:
        with open(input_path, "r", encoding="utf-8") as f:
            return f.read(), input_path
    return sys.stdin.read(), "stdin"

# Parse raw JSON text into (original_data, items_list).
def load_input(raw_text: str, logger: Optional[logging.Logger] = None) -> Tuple[Any, List[Any]]:
    raw_text = raw_text.strip()
    if not raw_text:
        if logger:
            logger.info("Input is empty after trimming; no items to process.")
        return [], []

    data = json.loads(raw_text)
    if isinstance(data, dict) and "items" in data:
        items = data["items"]
        if not isinstance(items, list):
            if logger:
                logger.error('Invalid input: "items" must be a list, got %s.', type(items).__name__)
            raise ValueError('"items" must be a list')
        if logger:
            logger.info('Parsed input as object with "items" list (%d items).', len(items))
        return data, items
    if isinstance(data, list):
        if logger:
            logger.info("Parsed input as list (%d items).", len(data))
        return data, data
    if logger:
        logger.info("Parsed input as a single item; wrapping into list.")
    return data, [data]

# Extract a text string from an item, supporting dicts and raw strings.
def extract_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        text = item.get("text")
        if text is None:
            return ""
        return text if isinstance(text, str) else str(text)
    return str(item)

# Preserve the input structure while replacing the items list.
def prepare_output(original_data: Any, output_items: List[Any]) -> Any:
    if isinstance(original_data, dict) and "items" in original_data:
        output_data = dict(original_data)
        output_data["items"] = output_items
        return output_data
    return output_items

# Write JSON output to a file or stdout.
def write_output(
    output_path: str,
    output_data: Any,
    logger: Optional[logging.Logger] = None,
    is_empty: bool = False,
) -> None:
    out_text = json.dumps(output_data, ensure_ascii=False)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(out_text)
    else:
        print(out_text)
    if logger:
        suffix = " (empty)" if is_empty else ""
        if output_path:
            logger.info("Output file: %s%s", output_path, suffix)
        else:
            logger.info("Output: stdout%s", suffix)
