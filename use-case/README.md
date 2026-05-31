# Android 11 Use Case And Evaluation Dataset

This folder documents and automates the evaluation use case for the Hate Speech Detector Autopsy plugin. The goal is to modify an existing Android forensic image with controlled, annotated messages, run Autopsy extraction again, and compare manual review with plugin results and processing time.

The base evidence source is the Android 11 phone image from Digital Corpora:

- Digital Corpora cell-phone images: https://digitalcorpora.org/corpora/cell-phones/

## Evaluation Scenario

The original Android 11 image was first opened and analyzed with Autopsy and the Android Analyzer plugin to inspect available artifacts. The image contains several social media and messaging applications, but most application databases contain only a small number of test messages.

Autopsy extracted 119 message artifacts marked as `TSK_MESSAGE`. These artifacts are used as input by the Hate Speech Detector plugin. The extracted messages are associated with the application labels identified during manual Autopsy review:

- Android SMS/MMS
- IMO
- Line
- WhatsApp
- TextNow
- Viber
- Facebook Messenger

Manual review and plugin review of the original extracted messages did not identify hate-speech messages. For a more useful evaluation, selected application databases were copied out of the image and modified by inserting annotated text examples.

## Dataset

The inserted messages come from the Davidson hate-speech dataset (`DS2_DavidsonDataset`). The prepared sample is:

- `BuildDavidsonBalancedSample/davidson_balanced_sample_600.json`

The sample contains 600 annotated messages:

- 100 hate/offensive examples
- 500 normal examples

The subset is balanced for evaluation purposes; see the [BuildDavidsonBalancedSample README](BuildDavidsonBalancedSample/README.md) for details.
The dataset was chosen because the messages were already annotated by human annotators, which makes it suitable as a controlled evaluation source.

## Database Targets

Messages are inserted into three Android application databases:

- SMS/MMS: copied from `Android11-Pixel3-Data/data/data/com.android.providers.telephony/databases/mmssms.db` to `MmsSmsMessageInserter/database/mmssms.db`
- WhatsApp: copied from `Android11-Pixel3-Data/data/data/com.whatsapp/databases/msgstore.db` to `WhatsAppMessageInserter/database/msgstore.db`
- Viber: copied from `Android11-Pixel3-Data/data/data/com.viber.voip/databases/viber_messages` to `ViberMessageInserter/database/viber_messages`

Original extracted database copies are kept in:

- `Android11-databases-original/`

Use copied databases for experiments. Do not overwrite the original extracted databases unless that is intentional.

## Main Script

The main orchestration script is:

- `main.py`

`main.py` does not insert SQLite rows directly. It splits `BuildDavidsonBalancedSample/davidson_balanced_sample_600.json` into three temporary JSON files and calls the app-specific inserters:

- first 200 messages -> `MmsSmsMessageInserter/insert_messages.py`
- second 200 messages -> `WhatsAppMessageInserter/insert_messages.py`
- last 200 messages -> `ViberMessageInserter/insert_messages.py`

Temporary split files are deleted automatically after the run. The original Davidson JSON file is not modified.

## Important Implementation Detail

The app-specific inserters only insert JSON items where `is_hate` is `true`. The balanced Davidson sample contains both hate/offensive and normal examples. To make the existing inserters write all selected messages, `main.py` marks every temporary split item as insertable by setting `is_hate` to `true` and stores the previous value in `original_is_hate`.

This preserves the original annotation while reusing the existing insertion logic.

## Default Conversation Targets

Default target conversations are:

- MMS/SMS: `thread_id = 15`
- WhatsApp: `chat._id = 2`
- Viber: `conversations._id = 1`

## Usage

Run a dry check without changing any database:

```bash
python3 main.py
```

Insert all 600 messages into the three databases:

```bash
python3 main.py --apply
```

Use different target conversation IDs:

```bash
python3 main.py --apply \
  --sms-thread-id 15 \
  --whatsapp-chat-row-id 2 \
  --viber-conversation-id 1
```

Use copied databases instead of the defaults:

```bash
python3 main.py --apply \
  --sms-db /tmp/mmssms.db \
  --whatsapp-db /tmp/msgstore.db \
  --viber-db /tmp/viber_messages
```

Append messages at the current time instead of placing them near existing history:

```bash
python3 main.py --apply --append-time
```

Use a custom Davidson sample file:

```bash
python3 main.py --source-json BuildDavidsonBalancedSample/davidson_balanced_sample_600.json
```

## App-Specific Inserters

Each app-specific inserter can also be run directly.

### SMS/MMS

Folder: `MmsSmsMessageInserter/`

Script:

```bash
python3 MmsSmsMessageInserter/insert_messages.py
```

The script inserts text messages into the Android `sms` table, updates SMS search indexing in `words`, and recalculates the target `threads` summary. By default it uses `thread_id = 15`.

### WhatsApp

Folder: `WhatsAppMessageInserter/`

Script:

```bash
python3 WhatsAppMessageInserter/insert_messages.py
```

The script supports both newer `message` and legacy `messages` WhatsApp schemas. It inserts text rows, updates available FTS search tables, and updates chat pointer/sort columns where the schema provides them. By default it uses `chat._id = 2`.

### Viber

Folder: `ViberMessageInserter/`

Script:

```bash
python3 ViberMessageInserter/insert_messages.py
```

The script inserts text rows into the Viber `messages` table and derives Viber-specific fields from existing messages in the target conversation. By default it uses `conversations._id = 1`.

## Timestamp And Direction Behavior

Each inserter keeps the message order from its input JSON. By default, timestamps are generated near existing conversation history. Message direction alternates as received, sent, received, sent, and so on.

When `--append-time` is used, inserted messages are placed at the current time, one second apart, so they appear together at the end of the selected conversation.
