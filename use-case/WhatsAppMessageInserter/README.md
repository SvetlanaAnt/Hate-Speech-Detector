# WhatsApp Message Inserter

This folder contains a small utility script for inserting test messages from a JSON input file into a local WhatsApp `msgstore.db` SQLite database.

The script reads the JSON file passed with `--json`, keeps entries where `is_hate` is `true`, and inserts their non-empty `text` values into the WhatsApp message table used by the target database in the same order as the JSON input. If `--json` is not provided, the script looks for `hate_messages.json`. Newer WhatsApp exports use `message`; older or migrated databases may still use `messages`. The script detects that at runtime.

By default, inserted messages are placed near existing messages in the selected chat, with small random time gaps. Direction always alternates as received, sent, received, sent, and so on. The script also writes to the matching FTS search table and updates chat pointer fields for the active schema.

## Files

- `insert_messages.py` - Python script that performs the database insert.
- `database/msgstore.db` - Target WhatsApp SQLite database.

## Input JSON Format

The input file must be a JSON object with a top-level `items` array. Each item intended for insertion must have `is_hate` set to `true` and a non-empty string in `text`. Other fields are ignored by this inserter.

```json
{
  "items": [
    {
      "id": 1,
      "text": "Example message",
      "is_hate": true
    }
  ]
}
```

## Safety

Work on a copy of `msgstore.db`. The script writes directly to the SQLite database when `--apply` is used.

If DB Browser for SQLite or another program has the database open, the script may fail with `database is locked`. Close the other program or save and close the database before running the script.

## Usage

Run a dry check without changing the database. In this mode, the script checks the JSON/database paths and counts insertable messages, but it does not open the database or validate the target chat row:

```bash
python3 insert_messages.py
```

Insert messages into the default chat, `chat._id = 2`, alternating received/sent:

```bash
python3 insert_messages.py --apply
```

Append messages at the current time instead of placing them near existing chat history:

```bash
python3 insert_messages.py --apply --append-time
```

Use a different chat row:

```bash
python3 insert_messages.py --apply --chat-row-id 3
```

Use custom input or database paths:

```bash
python3 insert_messages.py --json path/to/input.json --db path/to/msgstore.db --apply
```


## WhatsApp Schema Versions

Relative default paths are resolved from this folder.

WhatsApp `msgstore.db` schemas vary by app version. This folder has examples of both formats:

- `message` - newer schema, usually linked to `chat`.
- `messages` - legacy schema, usually linked to `chat_list`.

The script chooses `messages` when that table exists and has more rows than `message`. Otherwise, it uses `message`.

## `message` Table Schema

One supported WhatsApp database table has this schema:

```sql
CREATE TABLE message (
    _id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_row_id INTEGER NOT NULL,
    from_me INTEGER NOT NULL,
    key_id TEXT NOT NULL,
    sender_jid_row_id INTEGER,
    status INTEGER,
    broadcast INTEGER,
    recipient_count INTEGER,
    participant_hash TEXT,
    origination_flags INTEGER,
    origin INTEGER,
    timestamp INTEGER,
    received_timestamp INTEGER,
    receipt_server_timestamp INTEGER,
    message_type INTEGER,
    text_data TEXT,
    starred INTEGER,
    lookup_tables INTEGER,
    message_add_on_flags INTEGER,
    sort_id INTEGER NOT NULL DEFAULT 0
);
```

| Column | Type | Notes |
| --- | --- | --- |
| `_id` | INTEGER | Primary key, autoincrement. |
| `chat_row_id` | INTEGER | Target chat row ID. Required. |
| `from_me` | INTEGER | `0` for received messages, `1` for sent messages. Required. |
| `key_id` | TEXT | Unique WhatsApp message key. Required. |
| `sender_jid_row_id` | INTEGER | Sender JID row reference. |
| `status` | INTEGER | Message status. This script uses `0` for received and `13` for sent. |
| `broadcast` | INTEGER | Broadcast flag. |
| `recipient_count` | INTEGER | Recipient count. |
| `participant_hash` | TEXT | Participant hash, mainly relevant for group contexts. |
| `origination_flags` | INTEGER | Origination flags. |
| `origin` | INTEGER | Message origin value. |
| `timestamp` | INTEGER | Main message timestamp in milliseconds. Used for ordering. |
| `received_timestamp` | INTEGER | Device receive timestamp. Set for received messages; `0` for sent messages. |
| `receipt_server_timestamp` | INTEGER | Server receipt timestamp. Set for sent messages; `-1` for received messages. |
| `message_type` | INTEGER | Message type. This script inserts text messages with `0`. |
| `text_data` | TEXT | Message body text. |
| `starred` | INTEGER | Starred flag. |
| `lookup_tables` | INTEGER | Lookup table flags. |
| `message_add_on_flags` | INTEGER | Add-on flags. |
| `sort_id` | INTEGER | Sort order value. Required, default `0`. |

## What The Script Updates

For each hate message, the script inserts one row into the active WhatsApp message table.

For the modern `message` table, it inserts text into `message.text_data`, creates a `message_ftsv2` row, resequences `message.sort_id` for the target chat in default timestamp mode, and updates supported pointer columns on `chat`.

For the legacy `messages` table, it inserts text into `messages.data`, updates `messages_fts` when it exists, also writes `message_ftsv2` when it exists, and updates supported pointer fields on `chat_list` and `chat`.

Modern `chat` pointer updates use supported columns from:

- `last_message_row_id`
- `display_message_row_id`
- `last_message_sort_id`
- `display_message_sort_id`
- `sort_timestamp`

Legacy pointer updates set `chat_list.message_table_id`, `chat_list.last_message_table_id`, and `chat_list.sort_timestamp` when `chat_list` exists. They also set supported `chat` columns from `last_message_row_id`, `display_message_row_id`, and `sort_timestamp`.

## Timestamp Mode

Default mode places inserted messages near existing messages in the selected chat. Generated timestamps are always increasing, so sorting by message time keeps the same order as the JSON input.

The `--append-time` mode appends inserted messages at the current time, one second apart. This means they appear together at the end of the chat when sorted by time.

When messages are placed near existing history, the script resequences `sort_id` for that chat using timestamp order, so sorting by `sort_id` or message time produces the same chronological order.

## Sender Timestamp Rules

The script fills timestamp columns differently depending on message direction, matching the observed WhatsApp database pattern:

- Received messages: `from_me = 0`, `status = 0`, `received_timestamp` is set, and `receipt_server_timestamp = -1`.
- Sent messages: `from_me = 1`, `status = 13`, `received_timestamp = 0`, and `receipt_server_timestamp` is set.

The main `timestamp` column is still used for message ordering. The inserted rows alternate between the received and sent rules in JSON order.
