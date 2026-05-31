## Model Evaluation Tool

`model_evaluation/main.py` runs one or more catalog models against a dataset, calculates metrics when a label file is available, and prints a summary table. It can also save model outputs under `model_evaluation/outputs/`.

### What It Does

- Loads a TSV or JSON dataset.
- Loads ground-truth labels from a CSV file with `id,label` rows.
- Runs the selected models from `MODEL_CATALOG`.
- Calculates metrics for items that have labels.
- Prints a results table.
- Optionally saves per-model outputs with `--save-outputs`.

#todo ima li nesto da se ponavlja ovde da se izbrise

### Dataset Input

The tool does not define a default dataset. Pass a dataset with `--input` or
select a configured dataset slot with `--dataset-index`.

```bash
python3 model_evaluation/main.py --input model_evaluation/dataset/1-SemEval2020Task12/extended_test/test_a_tweets_all.tsv
```

### Custom Dataset And Labels

```bash
python3 model_evaluation/main.py --input model_evaluation/dataset/1-SemEval2020Task12/extended_test/test_a_tweets_all.tsv \
  --label-file model_evaluation/dataset/1-SemEval2020Task12/extended_test/test_a_labels_all.csv
```

### Dataset Slot

`--dataset-index` selects one of the dataset paths configured in
`DATASET_SLOTS` inside `model_evaluation/main.py`. When a slot has a configured
label file, the tool uses it automatically unless `--label-file` is passed.

```bash
python3 model_evaluation/main.py --dataset-index 1
```

| Index | Dataset                                                                                                | Local path                                                                         | Positive labels | Source                                                                                           |
| ----- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------ |
| 1     | SemEval-2020 Task 12: Multilingual Offensive Language Identification in Social Media (OffensEval 2020) | `model_evaluation/dataset/1-SemEval2020Task12/extended_test/test_a_tweets_all.tsv` | `OFF`           | https://zenodo.org/records/3950379                                                               |
| 2     | Davidson - Automated Hate Speech Detection and the Problem of Offensive Language                       | `model_evaluation/dataset/2-Davidson/data/labeled_data.csv`                        | `0`, `1`        | https://github.com/t-davidson/hate-speech-and-offensive-language                                 |
| 3     | A Benchmark Dataset for Learning to Intervene in Online Hate Speech - Gab                              | `model_evaluation/dataset/3-A-Benchmark-Dataset/data/gab.csv`                      | `1`             | https://github.com/jing-qian/A-Benchmark-Dataset-for-Learning-to-Intervene-in-Online-Hate-Speech |
| 4     | A Benchmark Dataset for Learning to Intervene in Online Hate Speech - Reddit                           | `model_evaluation/dataset/3-A-Benchmark-Dataset/data/reddit.csv`                   | `1`             | https://github.com/jing-qian/A-Benchmark-Dataset-for-Learning-to-Intervene-in-Online-Hate-Speech |

### One Model

```bash
python3 model_evaluation/main.py --input model_evaluation/dataset/1-SemEval2020Task12/extended_test/test_a_tweets_all.tsv \
  --models electra_hatexplain
```

### Multiple Models

```bash
python3 model_evaluation/main.py --input model_evaluation/dataset/1-SemEval2020Task12/extended_test/test_a_tweets_all.tsv \
  --models electra_hatexplain,roberta_dynabench_target
```

### Save Outputs

```bash
python3 model_evaluation/main.py --input model_evaluation/dataset/1-SemEval2020Task12/extended_test/test_a_tweets_all.tsv \
  --save-outputs
```

### Metrics And Labels

The label file should be a CSV file with `id,label` rows. A header row is
optional. Positive values treated as hate labels can be configured with:

```bash
python3 model_evaluation/main.py --input model_evaluation/dataset/1-SemEval2020Task12/extended_test/test_a_tweets_all.tsv \
  --label-pos-values OFF
```

`accuracy`, `precision`, `recall`, and `f1` are calculated only for items that
have a label in the label file. `hate_count` and `hate_rate` are always
calculated across all processed items.

### Evaluation Results

The tables below show the saved evaluation results for each configured dataset
slot and each model in `MODEL_CATALOG`. `hate_count` and `hate_rate` are model
predictions across all loaded items. `acc`, `prec`, `rec`, and `f1` are
calculated only on labeled items.

### DS1 - SemEval-2020 Task 12 / OffensEval 2020

Labeled examples: `5993`; positive labels: `3002`; negative labels: `2991`;
unlabeled examples: `2`; positive label value: `OFF`.

| Model                         | Items | Labeled | Hate count | Hate rate | Accuracy | Precision | Recall |     F1 |
| ----------------------------- | ----: | ------: | ---------: | --------: | -------: | --------: | -----: | -----: |
| `electra_hatexplain`          |  5995 |    5993 |        769 |    0.1283 |   0.6117 |    0.9389 | 0.2405 | 0.3829 |
| `roberta_dynabench_target`    |  5995 |    5993 |       1982 |    0.3306 |   0.7791 |    0.9233 | 0.6096 | 0.7343 |
| `roberta_twitter_hate_latest` |  5995 |    5993 |        527 |    0.0879 |   0.5793 |    0.9564 | 0.1679 | 0.2856 |
| `bert_hatexplain_cnerg`       |  5995 |    5993 |        590 |    0.0984 |   0.5859 |    0.9407 | 0.1849 | 0.3090 |

### DS2 - Davidson Hate/Offensive Language

Labeled examples: `24783`; positive labels: `20620`; negative labels: `4163`;
unlabeled examples: `0`; positive label values: `0`, `1`.

| Model                         | Items | Labeled | Hate count | Hate rate | Accuracy | Precision | Recall |     F1 |
| ----------------------------- | ----: | ------: | ---------: | --------: | -------: | --------: | -----: | -----: |
| `electra_hatexplain`          | 24783 |   24783 |      11570 |    0.4669 |   0.5955 |    0.9579 | 0.5375 | 0.6886 |
| `roberta_dynabench_target`    | 24783 |   24783 |      19880 |    0.8022 |   0.9319 |    0.9762 | 0.9411 | 0.9583 |
| `roberta_twitter_hate_latest` | 24783 |   24783 |      14659 |    0.5915 |   0.7484 |    0.9907 | 0.7043 | 0.8233 |
| `bert_hatexplain_cnerg`       | 24783 |   24783 |      14065 |    0.5675 |   0.6866 |    0.9569 | 0.6527 | 0.7761 |

### DS3 - Benchmark Dataset, Gab

Labeled examples: `33776`; positive labels: `14614`; negative labels: `19162`;
unlabeled examples: `0`; positive label value: `1`.

| Model                         | Items | Labeled | Hate count | Hate rate | Accuracy | Precision | Recall |     F1 |
| ----------------------------- | ----: | ------: | ---------: | --------: | -------: | --------: | -----: | -----: |
| `electra_hatexplain`          | 33776 |   33776 |      18548 |    0.5491 |   0.8386 |    0.7470 | 0.9481 | 0.8356 |
| `roberta_dynabench_target`    | 33776 |   33776 |      16250 |    0.4811 |   0.8520 |    0.7959 | 0.8850 | 0.8381 |
| `roberta_twitter_hate_latest` | 33776 |   33776 |      14274 |    0.4226 |   0.8511 |    0.8358 | 0.8163 | 0.8259 |
| `bert_hatexplain_cnerg`       | 33776 |   33776 |      18180 |    0.5383 |   0.8444 |    0.7574 | 0.9422 | 0.8397 |

### DS4 - Benchmark Dataset, Reddit

Labeled examples: `22309`; positive labels: `5257`; negative labels: `17052`;
unlabeled examples: `0`; positive label value: `1`.

| Model                         | Items | Labeled | Hate count | Hate rate | Accuracy | Precision | Recall |     F1 |
| ----------------------------- | ----: | ------: | ---------: | --------: | -------: | --------: | -----: | -----: |
| `electra_hatexplain`          | 22309 |   22309 |       6946 |    0.3114 |   0.8377 |    0.6178 | 0.8162 | 0.7033 |
| `roberta_dynabench_target`    | 22309 |   22309 |       6034 |    0.2705 |   0.8383 |    0.6367 | 0.7308 | 0.6805 |
| `roberta_twitter_hate_latest` | 22309 |   22309 |       4458 |    0.1998 |   0.8471 |    0.7070 | 0.5996 | 0.6489 |
| `bert_hatexplain_cnerg`       | 22309 |   22309 |       6857 |    0.3074 |   0.8405 |    0.6239 | 0.8138 | 0.7063 |
