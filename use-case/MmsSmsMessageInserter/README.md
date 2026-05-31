# MMS/SMS Message Inserter

This folder contains a utility script for inserting test messages from a JSON input file into a local Android `mmssms.db` SQLite database.

The script reads the JSON file passed with `--json`, keeps entries where `is_hate` is `true`, and inserts their non-empty `text` values into the `sms` table in the same order as the JSON input. If `--json` is not provided, the script looks for `hate_messages.json`. By default, inserted messages are placed near existing messages in the selected thread, with small random time gaps. Direction always alternates as received, sent, received, sent, and so on.

## Files

- `insert_messages.py` - Python script that performs the database insert.
- `database/mmssms.db` - Target Android SMS/MMS SQLite database.
- `database/mmssms.pdf` - Schema reference for this database.

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

## Usage

Run a dry check without changing the database:

```bash
python3 insert_messages.py
```

Insert messages into the default SMS thread, `thread_id = 15`, alternating received/sent:

```bash
python3 insert_messages.py --apply
```

Use a different thread:

```bash
python3 insert_messages.py --apply --thread-id 12
```

Use custom input or database paths:

```bash
python3 insert_messages.py --json path/to/input.json --db path/to/mmssms.db --apply
```

Append messages at the current time instead of placing them near existing thread history:

```bash
python3 insert_messages.py --apply --append-time
```

## Notes

Relative default paths are resolved from this folder. For this database, `thread_id = 15` maps to address `9198887386`. The script also updates `words` for SMS search indexing when that table exists and recalculates the `threads` summary after insertion, including existing MMS/PDU rows.
