import argparse
import csv
import json
import random
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

# Keep default paths relative to this script so it works from any current directory.
DEFAULT_INPUT = SCRIPT_DIR / "DS2_DavidsonDataset" / "data" / "labeled_data.csv"
DEFAULT_OUTPUT = SCRIPT_DIR / "davidson_balanced_sample_600.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract DS2 Davidson messages with a fixed normal/hate ratio."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to DS2 CSV.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to output JSON file.",
    )
    parser.add_argument(
        "--normal-count",
        type=int,
        default=500,
        help="Number of normal/neither messages to extract.",
    )
    parser.add_argument(
        "--hate-count",
        type=int,
        default=100,
        help="Number of hate_speech/offensive_language messages to extract.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used to shuffle extracted messages.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    items = []
    normal_seen = 0
    hate_seen = 0

    with input_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        id_field = reader.fieldnames[0] if reader.fieldnames else ""

        # Read rows in dataset order and keep only the requested number per class.
        for row in reader:
            cls = str(row.get("class", "")).strip()
            is_hate = cls in {"0", "1"}

            if is_hate:
                if hate_seen >= args.hate_count:
                    continue
                hate_seen += 1
            else:
                if cls != "2" or normal_seen >= args.normal_count:
                    continue
                normal_seen += 1

            items.append(
                {
                    "id": str(row.get(id_field, "")),
                    "text": row.get("tweet", ""),
                    "is_hate": is_hate,
                }
            )

            # Stop as soon as both class quotas are filled.
            if normal_seen >= args.normal_count and hate_seen >= args.hate_count:
                break

    # Fail loudly if the dataset does not contain enough examples for the request.
    if normal_seen < args.normal_count or hate_seen < args.hate_count:
        raise RuntimeError(
            "Not enough rows found: "
            f"normal={normal_seen}/{args.normal_count}, "
            f"hate_or_offensive={hate_seen}/{args.hate_count}"
        )

    # Shuffle after extraction so hate/offensive examples are not grouped together.
    random.Random(args.seed).shuffle(items)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({"items": items}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(items)} items to {output_path}")
    print(f"normal={normal_seen}, hate_or_offensive={hate_seen}")


if __name__ == "__main__":
    main()
