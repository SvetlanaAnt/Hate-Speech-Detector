# Hate Speech CLI

Standalone Python command-line application for hate-speech classification over JSON input. This project can be used directly from the terminal or packaged into an executable that the Autopsy Java plugin calls through stdin/stdout.

## Project Scope

`hatespeech-py` is independent from the Java Autopsy module. It owns:

- model catalog configuration;
- Hugging Face model loading;
- local model download;
- JSON input/output parsing;
- inference and output shaping;
- PyInstaller executable generation.

The Java plugin does not import this Python code directly. It only runs a built executable such as `hatespeech_cli_v1.exe`.

## Requirements

- Python 3.11 recommended.
- `pip install -r requirements.txt`
- Internet access is required only when downloading models or using `--model-source online`.

### Setup with Anaconda

```bash
conda create -n autopsy-env python=3.11
conda activate autopsy-env
pip install -r requirements.txt
```

### Setup with Python venv

macOS/Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## CLI Options

Required mode, choose one:

- `--model <alias>`: run one model.
- `--models <a,b,c>`: run multiple models; use `all` for all catalog entries.
- `--list-models`: print the model catalog and exit.
- `--audit-models`: load models and print their `id2label` mappings.
- `--download-models [aliases]`: download all or selected models and exit.

Common options:

- `--input <file>`: JSON input file; stdin is used when omitted.
- `--output <file>`: JSON output file; stdout is used when omitted.
- `--model-source <auto|offline|online>`: model loading mode.
- `--models-dir <dir>`: local model root for inference.
- `--download-dir <dir>`: local model root for downloads.
- `--batch-size <int>`: inference batch size.
- `--max-seq-length <int>`: tokenizer maximum sequence length.
- `--hate-threshold <float>`: threshold for score-based hate decisions.
- `--hate-label-id <int>`: explicit hate label ID; can be repeated.
- `--hate-label-name <str>`: explicit hate label name; can be repeated.
- `--use-cuda`: use CUDA when available.
- `--log-file <file>`: log file path.
- `--log-items`: log per-item results without full text.
- `--log-texts`: log full item text; sensitive.
- `--model-catalog <file>`: merge an external catalog JSON file.
- `--predictions`: group multi-model results under a `predictions` field.

## Quick Run

```bash
python3 main.py --model electra_hatexplain < data/messages.json
```

The command reads JSON from stdin and writes JSON to stdout.

## Input Format

The CLI accepts:

- an object with an `items` list;
- a plain list of items;
- a single item object.

Example:

```json
{
  "items": [
    { "id": 1, "id_artifact": 101, "text": "Hello" },
    { "id": 2, "id_artifact": 101, "text": "I hate you and your group." }
  ]
}
```

## Output Format

The output keeps the input shape where possible. Each item receives prediction fields.

```json
{
  "items": [
    {
      "id": 1,
      "id_artifact": 101,
      "text": "Hello",
      "label_id": 0,
      "label_name": "normal",
      "is_hate_speech": false,
      "hate_score": 0.02
    }
  ]
}
```

## Model Catalog

Models are defined in `src/config.py` under `MODEL_CATALOG`. Each entry has:

- `alias`: stable user-facing model name;
- `offline_model_id`: local folder path, usually `models/<alias>`;
- `online_model_id`: Hugging Face model identifier;
- `model_type`: loader hint such as `bert`, `roberta`, or `electra`;
- hate label defaults used when explicit label options are not provided.

| Alias | Hugging Face model | Description | Hate labels used |
| --- | --- | --- | --- |
| `electra_hatexplain` | [TehranNLP-org/electra-base-hateXplain](https://huggingface.co/TehranNLP-org/electra-base-hateXplain) | ELECTRA model fine-tuned on HateXplain. Good for broader screening because it treats both hateful and offensive predictions as positive detections, so it is useful when higher recall is preferred. | `hatespeech`, `offensive` |
| `roberta_dynabench_target` | [facebook/roberta-hate-speech-dynabench-r4-target](https://huggingface.co/facebook/roberta-hate-speech-dynabench-r4-target) | RoBERTa model released for the Dynabench hate speech detection target task. Strong general-purpose option when a balanced tradeoff between accuracy, precision, and recall is needed. | `hate` |
| `roberta_twitter_hate_latest` | [cardiffnlp/twitter-roberta-base-hate-latest](https://huggingface.co/cardiffnlp/twitter-roberta-base-hate-latest) | Twitter RoBERTa model fine-tuned as a binary hate speech classifier. Best suited for short social-media style posts such as tweets or brief comments. | `HATE` |
| `bert_hatexplain_cnerg` | [Hate-speech-CNERG/bert-base-uncased-hatexplain](https://huggingface.co/Hate-speech-CNERG/bert-base-uncased-hatexplain) | BERT model trained on HateXplain data from Gab and Twitter. A more conservative HateXplain-based option when fewer false positives are preferred. | `hate speech`, `hatespeech`, `hate`, `offensive` |

List configured models:

```bash
python3 main.py --list-models
```

Inspect model labels:

```bash
python3 main.py --audit-models --model-source offline
```

## Model Source

Use `--model-source` to control where the model is loaded from:

- `auto`: default; use the local model if present, otherwise fall back to the online Hugging Face ID.
- `offline`: require a local model folder and fail if it is missing.
- `online`: always use the Hugging Face ID.

Examples:

```bash
python3 main.py --model electra_hatexplain --model-source auto < data/messages.json
python3 main.py --model electra_hatexplain --model-source offline --models-dir models < data/messages.json
python3 main.py --model electra_hatexplain --model-source online < data/messages.json
```

`--models-dir` is the root folder for local models during inference. If `offline_model_id` is `models/electra_hatexplain` and `--models-dir D:\models`, the CLI loads `D:\models\electra_hatexplain`.

## Download Local Models

Download all catalog models:

```bash
python3 main.py --download-models --download-dir models
```

Download selected models:

```bash
python3 main.py --download-models electra_hatexplain,bert_hatexplain_cnerg --download-dir models
```

Download always uses `online_model_id` and writes each model into `<download-dir>/<alias>`.

## External Model Catalog

External catalogs are JSON lists with the same shape as `MODEL_CATALOG`. Legacy entries with only `model_id` are still accepted.

```json
[
  {
    "alias": "custom_hatexplain",
    "offline_model_id": "models/custom_hatexplain",
    "online_model_id": "TehranNLP-org/electra-base-hateXplain",
    "model_type": "electra",
    "description": "Custom catalog entry for HateXplain.",
    "hate_label_names": ["hatespeech", "offensive"],
    "hate_label_ids": []
  }
]
```

Run with an external catalog:

```bash
python3 main.py --model-catalog data/catalog.json --model custom_hatexplain < data/messages.json
```

## Build Executable

Build on Windows when the executable will be used by the Windows Autopsy plugin.

1. Activate the Python 3.11 environment.

2. Install dependencies:

```bash
pip install -r requirements.txt
pip install pyinstaller
```

3. Build without bundling local models into the executable:

```bash
pyinstaller --onefile --clean --noconfirm --name hatespeech_cli_v1 main.py
```

4. The Windows output is:

```text
dist\hatespeech_cli_v1\hatespeech_cli_v1.exe
```

5. Keep models outside the executable. Download them separately:

```bash
python main.py --download-models --download-dir models
```

6. If this executable is used by the Java plugin, copy `hatespeech_cli_v1.exe` into the plugin binary folder and configure the model folder in the plugin Global Settings.

## Startup example

```bash
python3 main.py --model electra_hatexplain --model-source offline --models-dir models --input data/messages.json --output hatespeech_output.json
```
