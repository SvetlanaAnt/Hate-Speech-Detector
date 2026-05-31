
import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_JSON = ROOT_DIR / "BuildDavidsonBalancedSample" / "davidson_balanced_sample_600.json"

TARGETS = [
    {
        "name": "MMS/SMS",
        "script": ROOT_DIR / "MmsSmsMessageInserter" / "insert_messages.py",
        "default_db": ROOT_DIR / "MmsSmsMessageInserter" / "database" / "mmssms.db",
        "db_arg": "--db",
        "id_arg": "--thread-id",
        "id_attr": "sms_thread_id",
        "db_attr": "sms_db",
        "slice_start": 0,
        "slice_end": 200,
        "json_name": "davidson_sms_first_200.json",
    },
    {
        "name": "WhatsApp",
        "script": ROOT_DIR / "WhatsAppMessageInserter" / "insert_messages.py",
        "default_db": ROOT_DIR / "WhatsAppMessageInserter" / "database" / "msgstore.db",
        "db_arg": "--db",
        "id_arg": "--chat-row-id",
        "id_attr": "whatsapp_chat_row_id",
        "db_attr": "whatsapp_db",
        "slice_start": 200,
        "slice_end": 400,
        "json_name": "davidson_whatsapp_second_200.json",
    },
    {
        "name": "Viber",
        "script": ROOT_DIR / "ViberMessageInserter" / "insert_messages.py",
        "default_db": ROOT_DIR / "ViberMessageInserter" / "database" / "viber_messages",
        "db_arg": "--db",
        "id_arg": "--conversation-id",
        "id_attr": "viber_conversation_id",
        "db_attr": "viber_db",
        "slice_start": 400,
        "slice_end": 600,
        "json_name": "davidson_viber_last_200.json",
    },
]


def resolve_path(path_value):
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def load_items(source_json):
    with open(source_json, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("Source JSON must contain a top-level list in the 'items' field.")
    if len(items) < 600:
        raise ValueError(f"Source JSON must contain at least 600 items; found {len(items)}.")

    return items[:600]


def insertable_chunk(items, start, end):
    chunk = []
    for item in items[start:end]:
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Item id={item.get('id')} does not contain non-empty text.")

        copied = dict(item)
        copied["text"] = text.strip()
        copied["original_is_hate"] = item.get("is_hate")
        copied["is_hate"] = True
        chunk.append(copied)

    if len(chunk) != 200:
        raise ValueError(f"Expected 200 items for slice {start}:{end}; got {len(chunk)}.")

    return {"items": chunk}


def write_chunk_json(temp_dir, target, items):
    chunk_path = temp_dir / target["json_name"]
    with open(chunk_path, "w", encoding="utf-8") as handle:
        json.dump(
            insertable_chunk(items, target["slice_start"], target["slice_end"]),
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")
    return chunk_path


def build_command(args, target, chunk_path):
    db_path = resolve_path(getattr(args, target["db_attr"])) if getattr(args, target["db_attr"]) else target["default_db"]
    command = [
        sys.executable,
        str(target["script"]),
        "--json",
        str(chunk_path),
        target["db_arg"],
        str(db_path),
        target["id_arg"],
        str(getattr(args, target["id_attr"])),
    ]

    if args.append_time:
        command.append("--append-time")
    if args.apply:
        command.append("--apply")

    return command


def run_target(args, target, chunk_path):
    command = build_command(args, target, chunk_path)
    print(f"\n=== {target['name']} ===", flush=True)
    print(shlex.join(command), flush=True)
    subprocess.run(command, cwd=ROOT_DIR, check=True)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Split davidson_balanced_sample_600.json into 3 groups of 200 messages "
            "and call the MMS/SMS, WhatsApp, and Viber inserters."
        )
    )
    parser.add_argument(
        "--source-json",
        default=str(DEFAULT_SOURCE_JSON),
        help="Path to davidson_balanced_sample_600.json.",
    )
    parser.add_argument("--sms-db", help="Override MMS/SMS database path.")
    parser.add_argument("--whatsapp-db", help="Override WhatsApp database path.")
    parser.add_argument("--viber-db", help="Override Viber database path.")
    parser.add_argument("--sms-thread-id", type=int, default=15, help="Target MMS/SMS thread_id.")
    parser.add_argument("--whatsapp-chat-row-id", type=int, default=2, help="Target WhatsApp chat._id.")
    parser.add_argument("--viber-conversation-id", type=int, default=1, help="Target Viber conversations._id.")
    parser.add_argument(
        "--append-time",
        action="store_true",
        help="Pass --append-time to all three inserters.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write all three databases. Without this flag, all inserters run dry checks.",
    )
    args = parser.parse_args()

    source_json = resolve_path(args.source_json)
    if not source_json.exists():
        sys.exit(f"Source JSON does not exist: {source_json}")

    for target in TARGETS:
        db_path = resolve_path(getattr(args, target["db_attr"])) if getattr(args, target["db_attr"]) else target["default_db"]
        if not db_path.exists():
            sys.exit(f"{target['name']} database does not exist: {db_path}")
        if not target["script"].exists():
            sys.exit(f"{target['name']} inserter does not exist: {target['script']}")

    items = load_items(source_json)
    print(f"Loaded source messages: {len(items)}", flush=True)
    print("Split plan: first 200 -> MMS/SMS, second 200 -> WhatsApp, last 200 -> Viber.", flush=True)
    if not args.apply:
        print("Dry run: databases will not be modified. Add --apply to write all three databases.", flush=True)

    with tempfile.TemporaryDirectory(prefix="davidson_inserter_") as temp_name:
        temp_dir = Path(temp_name)
        for target in TARGETS:
            chunk_path = write_chunk_json(temp_dir, target, items)
            run_target(args, target, chunk_path)


if __name__ == "__main__":
    main()
