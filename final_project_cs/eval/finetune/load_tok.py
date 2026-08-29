"""Manual tokenizer loader — works around a transformers 5.14.1 bug where
AutoTokenizer.from_pretrained()/PreTrainedTokenizerFast.from_pretrained()
raise ValueError("Couldn't instantiate the backend tokenizer...") even
though the underlying tokenizer.json is valid (confirmed by loading it
directly via tokenizers.Tokenizer.from_file()). Bypasses the broken
from_pretrained() path entirely.
"""
from __future__ import annotations

import json

from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer
from transformers import PreTrainedTokenizerFast


def load_tokenizer(model_id: str) -> PreTrainedTokenizerFast:
    tokenizer_json_path = hf_hub_download(model_id, "tokenizer.json")
    config_path = hf_hub_download(model_id, "tokenizer_config.json")
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    raw = Tokenizer.from_file(tokenizer_json_path)
    tok = PreTrainedTokenizerFast(
        tokenizer_object=raw,
        bos_token=cfg.get("bos_token"),
        eos_token=cfg.get("eos_token"),
        pad_token=cfg.get("pad_token") or cfg.get("eos_token"),
        unk_token=cfg.get("unk_token"),
        model_max_length=cfg.get("model_max_length", 32768),
    )
    if cfg.get("chat_template"):
        tok.chat_template = cfg["chat_template"]
    return tok
