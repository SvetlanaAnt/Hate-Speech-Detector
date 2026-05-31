
import argparse
import json
import random
import secrets
import sqlite3
import sys
import time
from pathlib import Path


DEFAULT_JSON = "hate_messages.json"
DEFAULT_DB = "database/msgstore.db"
SCRIPT_DIR = Path(__file__).resolve().parent
MIN_GAP_MS = 30 * 1000
MAX_GAP_MS = 7 * 60 * 1000


def table_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def table_exists(conn, table_name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def resolve_path(path_value):
    path = Path(path_value)
    if path.exists() or path.is_absolute():
        return path

    script_relative_path = SCRIPT_DIR / path
    if script_relative_path.exists():
        return script_relative_path

    return path


def table_count(conn, table_name):
    if not table_exists(conn, table_name):
        return 0
    row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0])


def use_legacy_messages_table(conn):
    return table_exists(conn, "messages") and table_count(conn, "messages") > table_count(conn, "message")


def load_hate_messages(json_path):
    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("JSON must contain a top-level list in the 'items' field.")

    messages = []
    for item in items:
        if item.get("is_hate") is True:
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                messages.append(text.strip())

    return messages


def ensure_chat_exists(conn, chat_row_id):
    row = conn.execute(
        "SELECT _id FROM chat WHERE _id = ?",
        (chat_row_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Chat with _id = {chat_row_id} does not exist.")


def next_sort_id(conn):
    row = conn.execute("SELECT COALESCE(MAX(sort_id), 0) + 1 FROM message").fetchone()
    return int(row[0])


def ordered_timestamps_near_history(existing_timestamps, count):
    if count == 0:
        return []

    if len(existing_timestamps) >= 2:
        anchor_index = random.randint(0, max(0, len(existing_timestamps) - 2))
        start_ms = existing_timestamps[anchor_index]
        next_ms = existing_timestamps[anchor_index + 1]
    elif len(existing_timestamps) == 1:
        start_ms = existing_timestamps[0]
        next_ms = start_ms + (count + 1) * MAX_GAP_MS
    else:
        start_ms = int(time.time() * 1000) - (24 * 60 * 60 * 1000)
        next_ms = start_ms + (count + 1) * MAX_GAP_MS

    required_span_ms = (count + 1) * MIN_GAP_MS
    if next_ms - start_ms < required_span_ms:
        next_ms = start_ms + required_span_ms

    cursor_ms = start_ms + random.randint(5 * 1000, MIN_GAP_MS)
    timestamps = []
    for remaining in range(count, 0, -1):
        latest_allowed = next_ms - ((remaining - 1) * MIN_GAP_MS) - 1
        cursor_ms = min(cursor_ms, latest_allowed)
        timestamps.append(cursor_ms)
        if remaining > 1:
            max_gap = min(MAX_GAP_MS, max(MIN_GAP_MS, latest_allowed - cursor_ms))
            cursor_ms += random.randint(MIN_GAP_MS, max_gap)

    return timestamps


def changed_timestamps(conn, chat_row_id, count):
    rows = conn.execute(
        """
        SELECT timestamp
        FROM message
        WHERE chat_row_id = ? AND timestamp IS NOT NULL
        ORDER BY timestamp, _id
        """,
        (chat_row_id,),
    ).fetchall()
    existing_timestamps = [int(row[0]) for row in rows]
    return ordered_timestamps_near_history(existing_timestamps, count)


def legacy_changed_timestamps(conn, key_remote_jid, count):
    rows = conn.execute(
        """
        SELECT timestamp
        FROM messages
        WHERE key_remote_jid = ? AND timestamp IS NOT NULL
        ORDER BY timestamp, _id
        """,
        (key_remote_jid,),
    ).fetchall()
    existing_timestamps = [int(row[0]) for row in rows]
    return ordered_timestamps_near_history(existing_timestamps, count)


def message_timestamps(timestamp_ms, from_me):
    server_offset_ms = random.randint(18 * 60 * 1000, 22 * 60 * 1000)

    if from_me:
        return {
            "timestamp": timestamp_ms,
            "received_timestamp": 0,
            "receipt_server_timestamp": timestamp_ms + server_offset_ms,
        }

    return {
        "timestamp": timestamp_ms,
        "received_timestamp": max(0, timestamp_ms - server_offset_ms),
        "receipt_server_timestamp": -1,
    }


def legacy_key_remote_jid(conn, chat_row_id):
    row = conn.execute(
        """
        SELECT jid.raw_string
        FROM chat
        JOIN jid ON jid._id = chat.jid_row_id
        WHERE chat._id = ?
        """,
        (chat_row_id,),
    ).fetchone()
    if row is not None and row[0]:
        return row[0]

    row = conn.execute(
        """
        SELECT key_remote_jid
        FROM chat_list
        WHERE _id = ?
        """,
        (chat_row_id,),
    ).fetchone()
    if row is not None and row[0]:
        return row[0]

    raise ValueError(f"Could not resolve key_remote_jid for chat._id = {chat_row_id}.")


def insert_legacy_message(conn, key_remote_jid, text, timestamp_ms, from_me):
    status = 13 if from_me else 0
    timestamps = message_timestamps(timestamp_ms, from_me)
    values = {
        "key_remote_jid": key_remote_jid,
        "key_from_me": 1 if from_me else 0,
        "key_id": secrets.token_hex(16).upper(),
        "status": status,
        "needs_push": 0,
        "data": text,
        "timestamp": timestamps["timestamp"],
        "media_wa_type": "0",
        "origin": 0,
        "received_timestamp": timestamps["received_timestamp"],
        "send_timestamp": timestamps["timestamp"] if from_me else -1,
        "receipt_server_timestamp": timestamps["receipt_server_timestamp"],
        "receipt_device_timestamp": -1,
        "read_device_timestamp": -1,
        "played_device_timestamp": -1,
        "recipient_count": 0,
        "starred": 0,
    }
    columns = [column for column in values if column in table_columns(conn, "messages")]
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    cursor = conn.execute(
        f"INSERT INTO messages ({column_list}) VALUES ({placeholders})",
        tuple(values[column] for column in columns),
    )
    message_id = cursor.lastrowid

    if table_exists(conn, "messages_fts"):
        conn.execute(
            "INSERT INTO messages_fts (docid, content) VALUES (?, ?)",
            (message_id, text.lower()),
        )
    if table_exists(conn, "message_ftsv2"):
        row = conn.execute(
            "SELECT 1 FROM message_ftsv2 WHERE docid = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            fts_jid = "1 f" if from_me else "0 f"
            conn.execute(
                "INSERT INTO message_ftsv2 (docid, content, fts_jid, fts_namespace) VALUES (?, ?, ?, '')",
                (message_id, text.lower(), fts_jid),
            )

    return message_id


def insert_message(conn, chat_row_id, text, timestamp_ms, sort_id, from_me, message_columns):
    status = 13 if from_me else 0
    fts_jid = "1 f" if from_me else "0 f"
    timestamps = message_timestamps(timestamp_ms, from_me)

    values = {
        "chat_row_id": chat_row_id,
        "from_me": 1 if from_me else 0,
        "key_id": secrets.token_hex(16).upper(),
        "sender_jid_row_id": 0,
        "status": status,
        "broadcast": 0,
        "recipient_count": 0,
        "origination_flags": 0,
        "origin": 0,
        "timestamp": timestamps["timestamp"],
        "received_timestamp": timestamps["received_timestamp"],
        "receipt_server_timestamp": timestamps["receipt_server_timestamp"],
        "message_type": 0,
        "text_data": text,
        "starred": 0,
        "lookup_tables": 0,
        "message_add_on_flags": 0,
        "sort_id": sort_id,
    }
    columns = [column for column in values if column in message_columns]
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    cursor = conn.execute(
        f"INSERT INTO message ({column_list}) VALUES ({placeholders})",
        tuple(values[column] for column in columns),
    )
    message_id = cursor.lastrowid

    row = conn.execute(
        "SELECT 1 FROM message_ftsv2 WHERE docid = ?",
        (message_id,),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO message_ftsv2 (docid, content, fts_jid, fts_namespace)
            VALUES (?, ?, ?, '')
            """,
            (message_id, text.lower(), fts_jid),
        )

    return message_id


def resequence_chat_sort_ids(conn, chat_row_id):
    rows = conn.execute(
        """
        SELECT _id
        FROM message
        WHERE chat_row_id = ?
        ORDER BY timestamp, _id
        """,
        (chat_row_id,),
    ).fetchall()
    base_row = conn.execute(
        """
        SELECT COALESCE(MIN(sort_id), 1)
        FROM message
        WHERE chat_row_id = ?
        """,
        (chat_row_id,),
    ).fetchone()
    base_sort_id = int(base_row[0])

    for offset, row in enumerate(rows):
        conn.execute(
            "UPDATE message SET sort_id = ? WHERE _id = ?",
            (base_sort_id + offset, row[0]),
        )


def update_chat_pointer(conn, chat_row_id, last_message_id, chat_columns):
    updates = []
    params = []

    if "last_message_row_id" in chat_columns:
        updates.append("last_message_row_id = ?")
        params.append(last_message_id)
    if "display_message_row_id" in chat_columns:
        updates.append("display_message_row_id = ?")
        params.append(last_message_id)
    if "last_message_sort_id" in chat_columns:
        updates.append("last_message_sort_id = (SELECT sort_id FROM message WHERE _id = ?)")
        params.append(last_message_id)
    if "display_message_sort_id" in chat_columns:
        updates.append("display_message_sort_id = (SELECT sort_id FROM message WHERE _id = ?)")
        params.append(last_message_id)
    if "sort_timestamp" in chat_columns:
        updates.append("sort_timestamp = (SELECT timestamp FROM message WHERE _id = ?)")
        params.append(last_message_id)

    if not updates:
        return

    params.append(chat_row_id)
    conn.execute(
        f"UPDATE chat SET {', '.join(updates)} WHERE _id = ?",
        tuple(params),
    )


def update_chat_pointer_to_latest(conn, chat_row_id, chat_columns):
    row = conn.execute(
        """
        SELECT _id
        FROM message
        WHERE chat_row_id = ?
        ORDER BY sort_id DESC, _id DESC
        LIMIT 1
        """,
        (chat_row_id,),
    ).fetchone()
    if row is not None:
        update_chat_pointer(conn, chat_row_id, row[0], chat_columns)


def update_legacy_chat_pointer(conn, chat_row_id, key_remote_jid, last_message_id):
    row = conn.execute(
        "SELECT timestamp FROM messages WHERE _id = ?",
        (last_message_id,),
    ).fetchone()
    if row is None:
        return
    timestamp_ms = row[0]

    if table_exists(conn, "chat_list"):
        conn.execute(
            """
            UPDATE chat_list
            SET
                message_table_id = ?,
                last_message_table_id = ?,
                sort_timestamp = ?
            WHERE key_remote_jid = ?
            """,
            (last_message_id, last_message_id, timestamp_ms, key_remote_jid),
        )

    chat_columns = table_columns(conn, "chat")
    updates = []
    params = []
    if "last_message_row_id" in chat_columns:
        updates.append("last_message_row_id = ?")
        params.append(last_message_id)
    if "display_message_row_id" in chat_columns:
        updates.append("display_message_row_id = ?")
        params.append(last_message_id)
    if "sort_timestamp" in chat_columns:
        updates.append("sort_timestamp = ?")
        params.append(timestamp_ms)
    if updates:
        params.append(chat_row_id)
        conn.execute(
            f"UPDATE chat SET {', '.join(updates)} WHERE _id = ?",
            tuple(params),
        )


def update_legacy_chat_pointer_to_latest(conn, chat_row_id, key_remote_jid):
    row = conn.execute(
        """
        SELECT _id
        FROM messages
        WHERE key_remote_jid = ?
        ORDER BY timestamp DESC, _id DESC
        LIMIT 1
        """,
        (key_remote_jid,),
    ).fetchone()
    if row is not None:
        update_legacy_chat_pointer(conn, chat_row_id, key_remote_jid, row[0])


def main():
    parser = argparse.ArgumentParser(
        description="Insert messages with is_hate=true from hate_messages.json into WhatsApp msgstore.db."
    )
    parser.add_argument("--json", default=DEFAULT_JSON, help="Path to the hate_messages.json file.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to the msgstore.db database.")
    parser.add_argument("--chat-row-id", type=int, default=2, help="Target chat._id for inserted messages.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write messages to the database. Without this flag the script only runs a dry check.",
    )
    parser.add_argument(
        "--append-time",
        action="store_true",
        help="Append inserted messages at the current time instead of placing them near existing chat history.",
    )
    args = parser.parse_args()

    json_path = resolve_path(args.json)
    db_path = resolve_path(args.db)
    if not json_path.exists():
        sys.exit(f"JSON file does not exist: {json_path}")
    if not db_path.exists():
        sys.exit(f"SQLite database does not exist: {db_path}")

    messages = load_hate_messages(json_path)
    print(f"Found messages with is_hate=true: {len(messages)}")

    if not args.apply:
        print("Dry run: the database was not modified. Add --apply to write the messages.")
        return

    with sqlite3.connect(db_path) as conn:
        ensure_chat_exists(conn, args.chat_row_id)
        legacy_mode = use_legacy_messages_table(conn)
        if legacy_mode:
            key_remote_jid = legacy_key_remote_jid(conn, args.chat_row_id)
            if args.append_time:
                base_timestamp_ms = int(time.time() * 1000)
                timestamps = [base_timestamp_ms + (offset * 1000) for offset in range(len(messages))]
            else:
                timestamps = legacy_changed_timestamps(conn, key_remote_jid, len(messages))

            last_message_id = None
            with conn:
                for offset, text in enumerate(messages):
                    last_message_id = insert_legacy_message(
                        conn=conn,
                        key_remote_jid=key_remote_jid,
                        text=text,
                        timestamp_ms=timestamps[offset],
                        from_me=offset % 2 == 1,
                    )

                if args.append_time and last_message_id is not None:
                    update_legacy_chat_pointer(conn, args.chat_row_id, key_remote_jid, last_message_id)
                else:
                    update_legacy_chat_pointer_to_latest(conn, args.chat_row_id, key_remote_jid)

            print(f"Inserted messages: {len(messages)}")
            print(f"Updated chat_row_id: {args.chat_row_id}")
            if args.append_time:
                print("Timestamps: inserted messages were appended at the current time.")
            else:
                print("Timestamps: inserted messages were placed in JSON order near existing chat messages.")
            print("Direction: messages were inserted alternately as received/sent.")
            return

        message_columns = table_columns(conn, "message")
        chat_columns = table_columns(conn, "chat")
        if args.append_time:
            base_timestamp_ms = int(time.time() * 1000)
            timestamps = [base_timestamp_ms + (offset * 1000) for offset in range(len(messages))]
        else:
            timestamps = changed_timestamps(conn, args.chat_row_id, len(messages))
        sort_id = next_sort_id(conn)

        last_message_id = None
        with conn:
            for offset, text in enumerate(messages):
                last_message_id = insert_message(
                    conn=conn,
                    chat_row_id=args.chat_row_id,
                    text=text,
                    timestamp_ms=timestamps[offset],
                    sort_id=sort_id + offset,
                    from_me=offset % 2 == 1,
                    message_columns=message_columns,
                )

            if args.append_time and last_message_id is not None:
                update_chat_pointer(conn, args.chat_row_id, last_message_id, chat_columns)
            else:
                resequence_chat_sort_ids(conn, args.chat_row_id)
                update_chat_pointer_to_latest(conn, args.chat_row_id, chat_columns)

    print(f"Inserted messages: {len(messages)}")
    print(f"Updated chat_row_id: {args.chat_row_id}")
    if args.append_time:
        print("Timestamps: inserted messages were appended at the current time.")
    else:
        print("Timestamps: inserted messages were placed in JSON order near existing chat messages.")
    print("Direction: messages were inserted alternately as received/sent.")


if __name__ == "__main__":
    main()
