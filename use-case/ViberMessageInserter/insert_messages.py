
import argparse
import json
import random
import secrets
import sqlite3
import sys
import time
from pathlib import Path


DEFAULT_JSON = "hate_messages.json"
DEFAULT_DB = "database/viber_messages"
DEFAULT_CONVERSATION_ID = 1
SCRIPT_DIR = Path(__file__).resolve().parent
MIN_GAP_MS = 30 * 1000
MAX_GAP_MS = 7 * 60 * 1000


def table_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def resolve_path(path_value):
    path = Path(path_value)
    if path.exists() or path.is_absolute():
        return path

    script_relative_path = SCRIPT_DIR / path
    if script_relative_path.exists():
        return script_relative_path

    return path


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


def ensure_conversation_exists(conn, conversation_id):
    row = conn.execute(
        "SELECT _id FROM conversations WHERE _id = ?",
        (conversation_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Conversation with _id = {conversation_id} does not exist.")


def changed_timestamps(conn, conversation_id, count):
    if count == 0:
        return []

    rows = conn.execute(
        """
        SELECT msg_date
        FROM messages
        WHERE conversation_id = ? AND msg_date IS NOT NULL
        ORDER BY msg_date, _id
        """,
        (conversation_id,),
    ).fetchall()
    existing_timestamps = [int(row[0]) for row in rows]

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


def conversation_values(conn, conversation_id):
    row = conn.execute(
        """
        SELECT conversation_type, group_id
        FROM conversations
        WHERE _id = ?
        """,
        (conversation_id,),
    ).fetchone()
    return {
        "conversation_type": int(row[0] or 0),
        "group_id": int(row[1] or 0),
    }


def participant_for_direction(conn, conversation_id, from_me):
    send_type = 1 if from_me else 0
    row = conn.execute(
        """
        SELECT participant_id
        FROM messages
        WHERE conversation_id = ? AND send_type = ? AND participant_id > 0
        GROUP BY participant_id
        ORDER BY COUNT(*) DESC, MAX(msg_date) DESC
        LIMIT 1
        """,
        (conversation_id, send_type),
    ).fetchone()
    if row is not None:
        return int(row[0])

    column = "participant_id_2" if from_me else "participant_id_1"
    row = conn.execute(
        f"SELECT {column} FROM conversations WHERE _id = ?",
        (conversation_id,),
    ).fetchone()
    if row is not None and row[0]:
        return int(row[0])

    row = conn.execute(
        """
        SELECT _id
        FROM participants
        WHERE conversation_id = ?
        ORDER BY _id
        LIMIT 1
        """,
        (conversation_id,),
    ).fetchone()
    if row is not None:
        return int(row[0])

    return 0


def user_id_for_conversation(conn, conversation_id):
    row = conn.execute(
        """
        SELECT user_id
        FROM messages
        WHERE conversation_id = ? AND user_id IS NOT NULL AND user_id != ''
        GROUP BY user_id
        ORDER BY COUNT(*) DESC, MAX(msg_date) DESC
        LIMIT 1
        """,
        (conversation_id,),
    ).fetchone()
    if row is not None:
        return row[0]

    row = conn.execute(
        """
        SELECT participants_info.member_id
        FROM participants
        JOIN participants_info ON participants_info._id = participants.participant_info_id
        WHERE participants.conversation_id = ?
          AND participants_info.member_id IS NOT NULL
          AND participants_info.member_id != ''
        ORDER BY participants._id DESC
        LIMIT 1
        """,
        (conversation_id,),
    ).fetchone()
    if row is not None:
        return row[0]

    return ""


def text_template(conn, conversation_id, from_me):
    send_type = 1 if from_me else 0
    row = conn.execute(
        """
        SELECT flag, extra_flags, status, opened, sync_read, spans
        FROM messages
        WHERE conversation_id = ? AND send_type = ? AND extra_mime = 0
        ORDER BY msg_date DESC, _id DESC
        LIMIT 1
        """,
        (conversation_id, send_type),
    ).fetchone()
    if row is not None:
        return {
            "flag": row[0],
            "extra_flags": row[1],
            "status": row[2],
            "opened": row[3],
            "sync_read": row[4],
            "spans": row[5],
        }

    return {
        "flag": 4096,
        "extra_flags": 512 if from_me else 0,
        "status": 2,
        "opened": 0,
        "sync_read": 0,
        "spans": "no_sp",
    }


def order_key_model(conn, conversation_id):
    rows = conn.execute(
        """
        SELECT msg_date, order_key
        FROM messages
        WHERE conversation_id = ?
          AND msg_date IS NOT NULL
          AND order_key IS NOT NULL
        ORDER BY msg_date
        """,
        (conversation_id,),
    ).fetchall()
    if len(rows) >= 2:
        first_date, first_key = int(rows[0][0]), int(rows[0][1])
        last_date, last_key = int(rows[-1][0]), int(rows[-1][1])
        if last_date != first_date:
            slope = (last_key - first_key) / (last_date - first_date)
            intercept = first_key - (slope * first_date)
            return slope, intercept
    if rows:
        date_ms, order_key = int(rows[-1][0]), int(rows[-1][1])
        return 4_194_304.0, order_key - (4_194_304.0 * date_ms)
    return 4_194_304.0, 0.0


def generated_order_key(timestamp_ms, slope, intercept, used_order_keys):
    order_key = int(round((slope * timestamp_ms) + intercept))
    order_key += random.randint(1, 4095)
    while order_key in used_order_keys:
        order_key += 1
    used_order_keys.add(order_key)
    return order_key


def generated_seq(conn):
    row = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM messages").fetchone()
    return int(row[0] or 0) + random.randint(1000, 100000)


def insert_viber_message(conn, conversation_id, text, timestamp_ms, from_me, context):
    participant_id = participant_for_direction(conn, conversation_id, from_me)
    send_type = 1 if from_me else 0
    template = text_template(conn, conversation_id, from_me)
    order_key = generated_order_key(
        timestamp_ms,
        context["slope"],
        context["intercept"],
        context["used_order_keys"],
    )
    token = order_key
    columns = table_columns(conn, "messages")
    values = {
        "conversation_id": conversation_id,
        "order_key": order_key,
        "msg_date": timestamp_ms,
        "token": token,
        "conversation_type": context["conversation_type"],
        "participant_id": participant_id,
        "unread": 0,
        "flag": template["flag"],
        "group_id": context["group_id"],
        "extra_flags": template["extra_flags"],
        "deleted": 0,
        "send_type": send_type,
        "extra_mime": 0,
        "user_id": context["user_id"],
        "seq": generated_seq(conn) if from_me else 0,
        "status": template["status"],
        "opened": template["opened"],
        "sync_read": template["sync_read"],
        "body": text,
        "msg_info": "{}",
        "event_count": 1,
        "likes_count": 0,
        "spans": template["spans"] or "no_sp",
        "timebomb": 0,
        "read_message_time": 0,
        "scroll_pos": 0,
        "broadcast_msg_id": 0,
        "my_reaction": 0,
    }
    insert_columns = [column for column in values if column in columns]
    placeholders = ", ".join("?" for _ in insert_columns)
    column_list = ", ".join(insert_columns)
    cursor = conn.execute(
        f"INSERT INTO messages ({column_list}) VALUES ({placeholders})",
        tuple(values[column] for column in insert_columns),
    )
    return cursor.lastrowid, token


def update_conversation_date(conn, conversation_id):
    row = conn.execute(
        """
        SELECT msg_date
        FROM messages
        WHERE conversation_id = ? AND deleted = 0
        ORDER BY msg_date DESC, _id DESC
        LIMIT 1
        """,
        (conversation_id,),
    ).fetchone()
    if row is not None:
        conn.execute(
            "UPDATE conversations SET date = ? WHERE _id = ?",
            (row[0], conversation_id),
        )


def main():
    parser = argparse.ArgumentParser(
        description="Insert messages with is_hate=true from hate_messages.json into Viber viber_messages SQLite database."
    )
    parser.add_argument("--json", default=DEFAULT_JSON, help="Path to the hate_messages.json file.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to the viber_messages database.")
    parser.add_argument(
        "--conversation-id",
        type=int,
        default=DEFAULT_CONVERSATION_ID,
        help="Target Viber conversations._id.",
    )
    parser.add_argument(
        "--append-time",
        action="store_true",
        help="Append inserted messages at the current time instead of placing them near existing conversation history.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write messages to the database. Without this flag the script only runs a dry check.",
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

    with sqlite3.connect(db_path) as conn:
        ensure_conversation_exists(conn, args.conversation_id)
        print(f"Target conversation_id: {args.conversation_id}")

        if not args.apply:
            print("Dry run: the database was not modified. Add --apply to write the messages.")
            return

        if args.append_time:
            base_timestamp_ms = int(time.time() * 1000)
            timestamps = [base_timestamp_ms + (offset * 1000) for offset in range(len(messages))]
        else:
            timestamps = changed_timestamps(conn, args.conversation_id, len(messages))

        slope, intercept = order_key_model(conn, args.conversation_id)
        used_order_keys = {
            int(row[0])
            for row in conn.execute(
                "SELECT order_key FROM messages WHERE order_key IS NOT NULL"
            ).fetchall()
        }
        conv_values = conversation_values(conn, args.conversation_id)
        context = {
            "conversation_type": conv_values["conversation_type"],
            "group_id": conv_values["group_id"],
            "user_id": user_id_for_conversation(conn, args.conversation_id),
            "slope": slope,
            "intercept": intercept,
            "used_order_keys": used_order_keys,
        }

        with conn:
            for offset, text in enumerate(messages):
                insert_viber_message(
                    conn=conn,
                    conversation_id=args.conversation_id,
                    text=text,
                    timestamp_ms=timestamps[offset],
                    from_me=offset % 2 == 1,
                    context=context,
                )
            update_conversation_date(conn, args.conversation_id)

    print(f"Inserted messages: {len(messages)}")
    if args.append_time:
        print("Timestamps: inserted messages were appended at the current time.")
    else:
        print("Timestamps: inserted messages were placed in JSON order near existing conversation messages.")
    print("Direction: messages were inserted alternately as received/sent.")


if __name__ == "__main__":
    main()
