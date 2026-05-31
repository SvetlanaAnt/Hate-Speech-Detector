# Hate Speech Detector Autopsy Module

Autopsy Data Source ingest module that analyzes extracted email and message artifacts for hate-speech indicators. The Java module does not run machine-learning code itself. It collects text from Autopsy artifacts, sends JSON to the packaged Python CLI executable, reads JSON predictions back, and creates Autopsy analysis results.

## Project Scope

`hatespeech` is the Java Autopsy plugin project. It owns:

- Autopsy ingest module registration;
- global plugin settings;
- per-ingest-job settings;
- collection of `TSK_EMAIL_MSG` and `TSK_MESSAGE` artifacts;
- invocation of the external Python executable;
- creation of `TSK_HATE_SPEECH_HIT` blackboard results;
- NBM packaging metadata.

The Python CLI is built separately from `hatespeech-py`.

## Key Classes

- `HateSpeechIngestModuleFactory`: registers the module, version, global settings panel, per-job settings panel, and Data Source ingest module.
- `HateSpeechGlobalSettings`: stores global plugin settings with `NbPreferences`.
- `HateSpeechGlobalSettingsPanel`: lets the user choose the local model folder, download models, and check model availability.
- `HateSpeechIngestJobSettings`: serializable per-job settings used by an ingest run.
- `HateSpeechIngestJobSettingsPanel`: UI shown when configuring an ingest job.
- `HateSpeechDataSourceIngestModule`: collects artifacts, calls the Python CLI, parses results, and posts analysis results.

## Processing Flow

1. Autopsy loads the module from the installed NBM.
2. The user configures global settings, including the local models folder.
3. The user starts an ingest job and chooses per-job settings, including model alias and model source.
4. The module collects selected email/message artifacts from the case blackboard.
5. The module builds JSON payload with text and source artifact IDs.
6. The module runs the packaged Python executable and sends JSON through stdin.
7. The Python executable returns JSON predictions through stdout.
8. The module creates `Hate Speech Hit` analysis results for items where `is_hate_speech=true`.

## Settings

### Global Settings

Global settings apply across ingest jobs:

- Local models folder.
- model execution timeout.
- selectable log file patterns for `hatespeech_YYYYMMDD_HHMMSS.log` and `evaluation_YYYYMMDD_HHMMSS.csv`.
- extended model settings: batch size, maximum sequence length, hate threshold, CUDA preference, and optional hate label IDs/names.
- `Download models`: runs the Python executable with `--download-models --download-dir <folder>`.
- `Check models`: checks whether expected model folders contain basic model files.

While models are downloading, the settings panel shows an indeterminate progress bar and disables model directory actions. Download output is logged to `logs/hatespeech_download_YYYYMMDD_HHMMSS.log` next to the selected models folder parent. The module also blocks ingest execution during the download and posts an Autopsy inbox message when the download completes or fails.

The models folder should contain one subfolder per model alias, for example:

```text
models/
  electra_hatexplain/
  roberta_dynabench_target/
  roberta_twitter_hate_latest/
  bert_hatexplain_cnerg/
```

### Per-Ingest-Job Settings

Per-job settings are selected for each ingest run:

- selected model alias;
- model source:
  - `auto`: use local model if present, otherwise use online Hugging Face ID;
  - `offline`: require local model, fail if missing;
  - `online`: always use online Hugging Face ID;
- selected model alias, including `all` to run every supported model in one ingest run;
- artifact source filters.

## Python Executable Location

The plugin locates the CLI executable through `InstalledFileLocator`.

Primary Windows path:

```text
modules/ext/hatespeech-bin/windows/hatespeech_cli_v1.exe
```

Recommended layout inside the built/installed module:

```text
modules/
  ext/
    hatespeech-bin/
      windows/
        hatespeech_cli_v1.exe
        models/
          electra_hatexplain/
          roberta_dynabench_target/
          roberta_twitter_hate_latest/
          bert_hatexplain_cnerg/
```

If another operating system is supported later, add an OS-specific executable location under the same `hatespeech-bin` structure, for example:

```text
modules/ext/hatespeech-bin/linux/hatespeech_cli_v1
modules/ext/hatespeech-bin/macos/hatespeech_cli_v1
```

The Java helper currently searches the Windows paths. Add new paths in `HateSpeechGlobalSettings.findCliExecutable()` when adding Linux or macOS support.

## CLI Invocation

The Java module passes these arguments to the executable:

```text
--model <alias>
--model-source <auto|offline|online>
--models-dir <configured_models_folder>
--log-file <case_module_dir>/HateSpeechDetector/hatespeech_YYYYMMDD_HHMMSS.log
--evaluation-log-file <case_module_dir>/HateSpeechDetector/evaluation_YYYYMMDD_HHMMSS.csv
--log-items
--log-texts
```

Conceptual example:

```bash
hatespeech_cli_v1.exe --model electra_hatexplain --model-source auto --models-dir <models_folder> --log-file <case_log> --evaluation-log-file <evaluation_csv> --log-items --log-texts
```

If `--evaluation-log-file` is omitted, the CLI writes `evaluation_YYYYMMDD_HHMMSS.csv` next to a timestamped `hatespeech_YYYYMMDD_HHMMSS.log`; otherwise it falls back to `evaluation.csv` in the same directory as `--log-file`. The file is CSV-formatted and contains one `ITEM` row per processed text, followed by `RUN_SUMMARY` rows with total runtime, min/max/average per-message processing time, and average message length in characters, words, and tokens. Per-message timing is estimated from measured batch runtime to preserve normal inference speed. If a ground-truth field is present in the input item, the log also writes TP/FN/FP/TN confusion classes and a `CONFUSION_MATRIX` summary row.

## Blackboard Output

Artifact type:

- `TSK_HATE_SPEECH_HIT` with display name `Hate Speech Hit`.

Score behavior:

- The module does not modify the original `TSK_MESSAGE` or `TSK_EMAIL_MSG` artifact score.
- For detected hate speech, it creates a linked analysis result with `Score.SCORE_NOTABLE`.
- The analysis result is linked back to the source artifact through `TSK_ASSOCIATED_ARTIFACT`.

Custom attributes:

- `TSK_HATE_SCORE`: model hate score.
- `TSK_HATE_MATCHED_TEXT`: text snippet, truncated to 250 characters.
- `TSK_HATE_MESSAGE_TYPE`: source type such as email, WhatsApp, Viber, or SMS.

Standard attributes:

- `TSK_ASSOCIATED_ARTIFACT`: source artifact ID.
- `TSK_PATH` and `TSK_PATH_SOURCE` when available.

The module also copies relevant email/message context attributes from the source artifact when present.

## NBM Metadata

Plugin metadata is declared in:

- `manifest.mf`: module code name and specification version.
- `Bundle.properties`: display name, category, short description, and long description.
- `nbproject/project.properties`: NBM author and license file.
- `LICENSE`: MIT license text.

## Build the NBM

Use NetBeans or the Autopsy module suite on a machine with the Autopsy platform configured.

Recommended NetBeans flow:

1. Open the `hatespeech/` project.
2. Confirm the Python executable is present under the module external files path, for example `modules/ext/hatespeech-bin/windows/hatespeech_cli_v1.exe`.
3. Build the project.
4. Create the NBM package from NetBeans.
5. The resulting `.nbm` file is the installable Autopsy plugin package.

Command-line builds depend on the local NetBeans/Autopsy platform setup. If Apache Ant is available and the NetBeans platform is configured, run from `hatespeech/`:

```bash
ant clean
ant nbm
```

## Install in Autopsy

1. Open Autopsy.
2. Go to `Tools -> Plugins`.
3. Open the `Downloaded` tab.
4. Click `Add Plugins...`.
5. Select the generated `.nbm` file.
6. Complete the install wizard.
7. Restart Autopsy if requested.

After installation:

1. Open or create a case.
2. Run ingest.
3. Select `Hate Speech Detector`.
4. Open `Global Settings` to choose/check/download local models.
5. Configure per-job settings and start ingest.

## Tests and Verification

Unit tests live under:

```text
test/unit/
```

Basic source-level verification:

```bash
javac -cp "<autopsy-and-dependency-jars>" -d /tmp/hatespeech_javac $(find src -name '*.java')
```

Full NBM verification should be done by installing the generated `.nbm` into Autopsy and running an ingest job on a test case.
