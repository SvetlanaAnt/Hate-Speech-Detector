# Build Davidson Balanced Sample

This script builds a smaller JSON sample from the Davidson dataset.

By default it creates:

- 500 normal / neither messages
- 100 hate speech or offensive language messages
- 600 messages total

The output format is:

```json
{
  "items": [
    {
      "id": "0",
      "text": "tweet text",
      "is_hate": false
    }
  ]
}
```

## Class Mapping

The Davidson dataset uses the `class` column:

```text
0 = hate_speech
1 = offensive_language
2 = neither
```

The full DS2 dataset contains 24,783 messages:

```text
hate_speech:          1,430
offensive_language:  19,190
neither:              4,163
```

The script maps the classes like this:

```text
class 0 or 1 -> is_hate: true
class 2      -> is_hate: false
```

## How To Run

From the project root:

```bash
python3 dataset/build_davidson_balanced_sample.py
```

This writes:

```text
dataset/davidson_balanced_sample_600.json
```

## Options

Use a different number of normal and hate/offensive messages:

```bash
python3 dataset/build_davidson_balanced_sample.py --normal-count 500 --hate-count 100
```

Use a different output file:

```bash
python3 dataset/build_davidson_balanced_sample.py --output dataset/my_sample.json
```

Use a different random shuffle seed:

```bash
python3 dataset/build_davidson_balanced_sample.py --seed 7
```

The seed controls the shuffled order of messages. The same seed gives the same output order every time.

## Input

The default input file is:

```text
dataset/2-Davidson/data/labeled_data.csv
```

To use a different CSV file:

```bash
python3 dataset/build_davidson_balanced_sample.py --input path/to/labeled_data.csv
```
