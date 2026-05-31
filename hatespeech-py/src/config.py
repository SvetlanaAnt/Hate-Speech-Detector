
# Default model selection and runtime parameters.
DEFAULT_MODEL = "electra_hatexplain"
DEFAULT_MODEL_TYPE = "electra"
DEFAULT_BATCH_SIZE = 32
DEFAULT_MAX_SEQ_LENGTH = 512
DEFAULT_LOG_FILE = "logs/hatespeech.log"
ALLOWED_MODEL_TYPES = {"auto", "bert", "roberta", "electra", "bertweet"}

# Output label names used by the CLI.
DEFAULT_LABEL_HATE = "hatespeech"
DEFAULT_LABEL_NORMAL = "normal"

# Model catalog used for CLI selection and UI descriptions.
MODEL_CATALOG = [
    {
        "alias": "electra_hatexplain",
        "offline_model_id": "models/electra_hatexplain",
        "online_model_id": "TehranNLP-org/electra-base-hateXplain",
        "model_type": "electra",
        "description": "Good choice for broader screening. Tends to flag more potentially hateful or offensive content and is useful when higher recall is preferred over stricter precision.\nModel: google/electra-base-discriminator fine-tuned on the HateXplain dataset.",
        "hate_label_names": ["hatespeech", "offensive"],
        "hate_label_ids": [0, 2],
    },
    {
        "alias": "roberta_dynabench_target",
        "offline_model_id": "models/roberta_dynabench_target",
        "online_model_id": "facebook/roberta-hate-speech-dynabench-r4-target",
        "model_type": "roberta",
        "description": "Strong general-purpose option for hate speech detection, especially when you want a balanced tradeoff between accuracy, precision, and recall.\nModel: Facebook RoBERTa model released for dynamically generated online hate detection data in the R4 target setting.",
        "hate_label_names": ["hate"],
        "hate_label_ids": [1],
    },
    {
        "alias": "roberta_twitter_hate_latest",
        "offline_model_id": "models/roberta_twitter_hate_latest",
        "online_model_id": "cardiffnlp/twitter-roberta-base-hate-latest",
        "model_type": "roberta",
        "description": "Well suited for short social-media style posts. Often more precise on concise, platform-like messages such as tweets or brief comments.\nModel: cardiffnlp/twitter-roberta-base-2022-154m fine-tuned as a binary hate-speech classifier on a combination of 13 English hate-speech datasets.",
        "hate_label_names": ["HATE"],
        "hate_label_ids": [1],
    },
    {
        "alias": "bert_hatexplain_cnerg",
        "offline_model_id": "models/bert_hatexplain_cnerg",
        "online_model_id": "Hate-speech-CNERG/bert-base-uncased-hatexplain",
        "model_type": "bert",
        "description": "More conservative HateXplain-based option. Useful when you want stronger precision and fewer false positives, especially on explicit abusive language.\nModel: bert-base-uncased classifier trained on the HateXplain dataset from Gab and Twitter, with human rationales incorporated during training.",
        "hate_label_names": ["hate speech", "hatespeech", "hate", "offensive"],
        "hate_label_ids": [0, 2],
    }
]
