# Viber Message Inserter

This folder contains a utility script for inserting test messages from a JSON input file into a local Viber `viber_messages` SQLite database.

The script reads the JSON file passed with `--json`, keeps entries where `is_hate` is `true`, and inserts their non-empty `text` values into the Viber `messages` table in the same order as the JSON input. If `--json` is not provided, the script looks for `hate_messages.json`. By default, inserted messages are placed near existing messages in the selected conversation, with small random time gaps. Direction always alternates as received, sent, received, sent, and so on.

## Files

- `insert_messages.py` - Python script that performs the database insert.
- `database/viber_messages` - Target Viber SQLite database.
- `database/viber_messages.pdf` - Schema reference for this database.

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

Insert messages into the default Viber conversation, `conversation_id = 1`, alternating received/sent:

```bash
python3 insert_messages.py --apply
```

Use a different conversation:

```bash
python3 insert_messages.py --apply --conversation-id 2
```

Use custom input or database paths:

```bash
python3 insert_messages.py --json path/to/input.json --db path/to/viber_messages --apply
```

Append messages at the current time instead of placing them near existing conversation history:

```bash
python3 insert_messages.py --apply --append-time
```

## Notes

Relative default paths are resolved from this folder.

The script exits if the JSON file, SQLite database, or selected conversation does not exist. Without `--apply`, it only validates the inputs and prints how many hate messages were found.

For this database, `conversation_id = 1` is the default conversation. The script derives Viber-specific values such as participant ID, `conversation_type`, `group_id`, `user_id`, `order_key`, `token`, flags, status, and read fields from existing rows in that conversation, then updates the conversation date after insertion. The first inserted message is received (`send_type = 0`), the second is sent (`send_type = 1`), and the pattern repeats.
