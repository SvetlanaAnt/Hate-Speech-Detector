
import argparse
import json
import random
import sqlite3
import sys
import time
from pathlib import Path


DEFAULT_JSON = "hate_messages.json"
DEFAULT_DB = "database/mmssms.db"
DEFAULT_THREAD_ID = 15
DEFAULT_CREATOR = "com.google.android.apps.messaging"
SCRIPT_DIR = Path(__file__).resolve().parent
MIN_GAP_MS = 30 * 1000
MAX_GAP_MS = 7 * 60 * 1000


# Proverava da li u SQLite bazi postoji tabela ili view sa zadatim imenom.
def table_exists(conn, table_name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


# Vraca skup svih kolona iz date tabele, da bi skripta mogla da radi i ako se
# shema malo razlikuje izmedju Android/Google Messages verzija.
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


# Ucitava JSON i izdvaja samo poruke obelezene sa is_hate=true.
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
            if isinstance(text, str):
                text = text.strip()
                if text:
                    messages.append(text)
    return messages


# Zaustavlja skriptu ako ciljani SMS thread ne postoji u tabeli threads.
def ensure_thread_exists(conn, thread_id):
    row = conn.execute(
        "SELECT _id FROM threads WHERE _id = ?",
        (thread_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Thread with _id = {thread_id} does not exist.")


# Pronalazi telefonski broj/adresu za dati thread. Prvo koristi postojece SMS
# redove, a ako ih nema, pada nazad na threads.recipient_ids -> canonical_addresses.
def thread_address(conn, thread_id):
    # Najbrze uzima adresu iz vec postojecih SMS poruka u thread-u. Ako postoji
    # vise adresa, bira onu koja se najcesce pojavljuje, pa najskorije koriscenu.
    row = conn.execute(
        """
        SELECT address
        FROM sms
        WHERE thread_id = ? AND address IS NOT NULL AND address != ''
        GROUP BY address
        ORDER BY COUNT(*) DESC, MAX(date) DESC
        LIMIT 1
        """,
        (thread_id,),
    ).fetchone()
    if row is not None:
        return row[0]

    # Ako thread nema SMS redove sa adresom, adresu cita iz metapodataka thread-a:
    # threads.recipient_ids pokazuje na canonical_addresses._id.
    row = conn.execute(
        """
        SELECT canonical_addresses.address
        FROM threads
        JOIN canonical_addresses ON canonical_addresses._id = CAST(threads.recipient_ids AS INTEGER)
        WHERE threads._id = ?
        """,
        (thread_id,),
    ).fetchone()
    if row is not None:
        return row[0]

    raise ValueError(f"Could not resolve SMS address for thread_id = {thread_id}.")


# Generise rastuce timestamp-e u blizini postojecih poruka u ciljanom thread-u.
# Time se cuva redosled poruka iz input JSON-a kada Android sortira po date.
def changed_timestamps(conn, thread_id, count):
    if count == 0:
        return []

    rows = []
    if table_exists(conn, "pdu"):
        rows = conn.execute(
            """
            SELECT date
            FROM (
                SELECT date
                FROM sms
                WHERE thread_id = ? AND date IS NOT NULL
                UNION ALL
                SELECT date * 1000 AS date
                FROM pdu
                WHERE thread_id = ? AND date IS NOT NULL
            )
            ORDER BY date
            """,
            (thread_id, thread_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT date
            FROM sms
            WHERE thread_id = ? AND date IS NOT NULL
            ORDER BY date
            """,
            (thread_id,),
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
    available_span_ms = next_ms - start_ms
    if available_span_ms < required_span_ms:
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


# Uzima pomocne vrednosti iz postojece poruke istog tipa u thread-u. Tako nove
# poruke zadrzavaju lokalni stil baze: sub_id, creator, service center i slicno.
def sample_sms_values(conn, thread_id, sms_type):
    row = conn.execute(
        """
        SELECT sub_id, creator, service_center, protocol, reply_path_present
        FROM sms
        WHERE thread_id = ? AND type = ?
        ORDER BY date DESC, _id DESC
        LIMIT 1
        """,
        (thread_id, sms_type),
    ).fetchone()
    if row is not None:
        return {
            "sub_id": row[0],
            "creator": row[1],
            "service_center": row[2],
            "protocol": row[3],
            "reply_path_present": row[4],
        }

    row = conn.execute(
        """
        SELECT sub_id, creator, service_center, protocol, reply_path_present
        FROM sms
        WHERE thread_id = ?
        ORDER BY date DESC, _id DESC
        LIMIT 1
        """,
        (thread_id,),
    ).fetchone()
    if row is not None:
        return {
            "sub_id": row[0],
            "creator": row[1],
            "service_center": row[2],
            "protocol": row[3],
            "reply_path_present": row[4],
        }

    return {
        "sub_id": -1,
        "creator": DEFAULT_CREATOR,
        "service_center": None,
        "protocol": None,
        "reply_path_present": None,
    }


# Ubacuje jednu SMS poruku u tabelu sms i, ako postoji, dodaje je u words FTS
# indeks koji Android koristi za pretragu poruka.
def insert_sms(conn, thread_id, address, text, timestamp_ms, from_me):
    sms_type = 2 if from_me else 1
    sample = sample_sms_values(conn, thread_id, sms_type)
    sms_columns = table_columns(conn, "sms")
    # Kod poslatih SMS poruka date_sent je u ovoj bazi 0; kod primljenih je malo
    # pre glavnog date timestamp-a, kao kod postojecih primljenih poruka.
    date_sent = 0 if from_me else max(0, timestamp_ms - random.randint(100, 2000))

    values = {
        "thread_id": thread_id,
        "address": address,
        "person": None,
        "date": timestamp_ms,
        "date_sent": date_sent,
        "protocol": sample["protocol"] if sample["protocol"] is not None else (None if from_me else 0),
        "read": 1,
        "status": -1,
        "type": sms_type,
        "reply_path_present": sample["reply_path_present"]
        if sample["reply_path_present"] is not None
        else (None if from_me else 0),
        "subject": None,
        "body": text,
        "service_center": sample["service_center"],
        "locked": 0,
        "sub_id": sample["sub_id"] if sample["sub_id"] is not None else -1,
        "error_code": -1,
        "creator": sample["creator"] or DEFAULT_CREATOR,
        "seen": 1,
    }
    # Ne upisujemo tvrdo kodiranu listu kolona; koristimo samo kolone koje ova
    # konkretna mmssms.db shema stvarno ima.
    columns = [column for column in values if column in sms_columns]
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    cursor = conn.execute(
        f"INSERT INTO sms ({column_list}) VALUES ({placeholders})",
        tuple(values[column] for column in columns),
    )
    sms_id = cursor.lastrowid

    if table_exists(conn, "words"):
        conn.execute(
            "INSERT INTO words (index_text, source_id, table_to_use) VALUES (?, ?, 1)",
            (text, sms_id),
        )

    return sms_id


# Racuna ukupan broj vidljivih poruka u thread-u: SMS redovi plus MMS/PDU redovi
# koje Android triggeri takodje racunaju u threads.message_count.
def sms_message_count(conn, thread_id):
    row = conn.execute(
        "SELECT COUNT(*) FROM sms WHERE thread_id = ? AND type != 3",
        (thread_id,),
    ).fetchone()
    count = int(row[0])

    if table_exists(conn, "pdu"):
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM pdu
            WHERE thread_id = ?
              AND (m_type = 132 OR m_type = 130 OR m_type = 128)
              AND msg_box != 3
            """,
            (thread_id,),
        ).fetchone()
        count += int(row[0])

    return count


# Rekonstrise summary red u tabeli threads posle ubacivanja. Ovo je potrebno jer
# Android triggeri pri insertu stave threads.date na trenutno vreme, sto nije
# tacno kada poruke namerno ubacujemo u istorijski vremenski opseg.
def update_thread_summary(conn, thread_id):
    message_count = sms_message_count(conn, thread_id)
    unread_sms = conn.execute(
        "SELECT COUNT(*) FROM sms WHERE thread_id = ? AND read = 0",
        (thread_id,),
    ).fetchone()[0]
    unread_pdu = 0
    if table_exists(conn, "pdu"):
        unread_pdu = conn.execute(
            """
            SELECT COUNT(*)
            FROM pdu
            WHERE thread_id = ?
              AND read = 0
              AND (m_type = 132 OR m_type = 130 OR m_type = 128)
            """,
            (thread_id,),
        ).fetchone()[0]

    if table_exists(conn, "pdu"):
        # MMS datumi u pdu tabeli su u sekundama, dok sms.date koristi milisekunde.
        # Zato za pdu koristimo date * 1000 pre poredjenja sa SMS porukama.
        latest = conn.execute(
            """
            SELECT date, snippet, snippet_cs
            FROM (
                SELECT date, body AS snippet, 0 AS snippet_cs, _id
                FROM sms
                WHERE thread_id = ? AND type != 3
                UNION ALL
                SELECT date * 1000 AS date, sub AS snippet, sub_cs AS snippet_cs, _id
                FROM pdu
                WHERE thread_id = ?
                  AND (m_type = 132 OR m_type = 130 OR m_type = 128)
                  AND msg_box != 3
            )
            ORDER BY date DESC, _id DESC
            LIMIT 1
            """,
            (thread_id, thread_id),
        ).fetchone()
    else:
        latest = conn.execute(
            """
            SELECT date, body AS snippet, 0 AS snippet_cs
            FROM sms
            WHERE thread_id = ? AND type != 3
            ORDER BY date DESC, _id DESC
            LIMIT 1
            """,
            (thread_id,),
        ).fetchone()

    if latest is None:
        return

    conn.execute(
        """
        UPDATE threads
        SET date = ?,
            snippet = ?,
            snippet_cs = ?,
            message_count = ?,
            read = ?
        WHERE _id = ?
        """,
        (
            latest[0],
            latest[1],
            latest[2] or 0,
            message_count,
            1 if unread_sms == 0 and unread_pdu == 0 else 0,
            thread_id,
        ),
    )


# Glavna CLI metoda: cita argumente, radi dry-run po defaultu, a uz --apply
# ubacuje poruke u izabrani thread i na kraju popravlja threads summary.
def main():
    parser = argparse.ArgumentParser(
        description="Insert messages with is_hate=true from hate_messages.json into Android mmssms.db."
    )
    parser.add_argument("--json", default=DEFAULT_JSON, help="Path to the hate_messages.json file.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to the mmssms.db database.")
    parser.add_argument("--thread-id", type=int, default=DEFAULT_THREAD_ID, help="Target sms.thread_id.")
    parser.add_argument(
        "--append-time",
        action="store_true",
        help="Append inserted messages at the current time instead of mixing them into existing thread history.",
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
        ensure_thread_exists(conn, args.thread_id)
        address = thread_address(conn, args.thread_id)
        print(f"Target thread_id: {args.thread_id}")
        print(f"Target address: {address}")

        if not args.apply:
            print("Dry run: the database was not modified. Add --apply to write the messages.")
            return

        if args.append_time:
            base_timestamp_ms = int(time.time() * 1000)
            timestamps = [base_timestamp_ms + (offset * 1000) for offset in range(len(messages))]
        else:
            # Podrazumevano se timestamp-i stavljaju redom blizu postojece istorije.
            timestamps = changed_timestamps(conn, args.thread_id, len(messages))

        with conn:
            for offset, text in enumerate(messages):
                insert_sms(
                    conn=conn,
                    thread_id=args.thread_id,
                    address=address,
                    text=text,
                    timestamp_ms=timestamps[offset],
                    from_me=offset % 2 == 1,
                )
            update_thread_summary(conn, args.thread_id)

    print(f"Inserted messages: {len(messages)}")
    if args.append_time:
        print("Timestamps: inserted messages were appended at the current time.")
    else:
        print("Timestamps: inserted messages were placed in JSON order near existing thread messages.")
    print("Direction: messages were inserted alternately as received/sent.")


if __name__ == "__main__":
    main()
