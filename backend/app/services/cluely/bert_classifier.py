"""
bert_classifier.py — Question vs. statement classifier for the overlay pipeline.

Model
-----
Uses `shahrukhx01/question-vs-statement-roberta` (HuggingFace), a fine-tuned
RoBERTa binary classifier.  On first use the model (~500 MB) is downloaded
to ~/.devcore/models/question-classifier in a daemon thread so startup is
never blocked.  The regex heuristic is active until the model is ready, then
swaps in automatically without a restart.

Fallback chain
--------------
  BERT model (preferred) → regex heuristic (always available)
"""

import asyncio
import logging
import os
import threading
from typing import Callable

from app.core.exceptions import BertClassifierError

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = os.path.expanduser("~/.devcore/models/question-classifier")
# Public HuggingFace model: NLI cross-encoder (~80 MB, no auth required).
# We run it as a zero-shot classifier with labels ["question", "statement"].
_HF_MODEL_ID = "cross-encoder/nli-distilroberta-base"

import re

_QUESTION_RE = re.compile(
    r'\b(what|who|where|when|why|how|which|whose|whom|can you|could you|'
    r'would you|tell me|explain|describe|have you|do you|are you|is there)\b',
    re.IGNORECASE,
)


def _regex_is_question(text: str) -> bool:
    """Heuristic fallback: question mark OR interrogative opener."""
    return text.strip().endswith("?") or bool(_QUESTION_RE.match(text.strip()))


class BertClassifier:
    """
    Classifies text as a question or a statement.

    Lifecycle
    ---------
    1. __init__ checks for the model on disk.
    2. If found → load immediately, use BERT for all calls.
    3. If missing → use regex, trigger a background download.
    4. When the download completes → hot-swap from regex to BERT.
       No restart required.
    """

    def __init__(self, model_path: str = _DEFAULT_MODEL_PATH) -> None:
        self._model_path = model_path
        self._pipe = None
        self._use_regex = True
        self._downloading = False
        # Callbacks registered by callers who want notification on model load.
        self._on_load_callbacks: list[Callable[[], None]] = []

        if os.path.exists(model_path):
            self._load_model()
        else:
            logger.info(
                "[bert] Model not found at %s — activating regex fallback and "
                "starting one-time background download from HuggingFace.",
                model_path,
            )
            self._start_background_download()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def using_bert(self) -> bool:
        return not self._use_regex

    async def is_question(self, text: str) -> bool:
        """
        Returns True if *text* is a question.
        Uses BERT when available, regex otherwise.
        ~10 ms on CPU (BERT) / <1 ms (regex).
        """
        if self._use_regex:
            return _regex_is_question(text)

        def _run() -> bool:
            result = self._pipe(text, candidate_labels=["question", "statement"])
            # zero-shot returns labels sorted by score descending.
            top_label: str = result["labels"][0].lower()
            return top_label == "question"

        return await asyncio.to_thread(_run)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Load the pipeline from disk. Raises BertClassifierError on failure."""
        try:
            from transformers import pipeline  # type: ignore

            # zero-shot-classification pipeline: given a text and candidate labels,
            # returns the label most entailed by the text.
            self._pipe = pipeline(
                "zero-shot-classification",
                model=self._model_path,
                device=-1,          # CPU
            )
            self._use_regex = False
            logger.info("[bert] NLI question-classifier loaded from %s", self._model_path)
            for cb in self._on_load_callbacks:
                try:
                    cb()
                except Exception:
                    pass
        except Exception as exc:
            raise BertClassifierError() from exc

    # ------------------------------------------------------------------
    # Background download
    # ------------------------------------------------------------------

    def _start_background_download(self) -> None:
        if self._downloading:
            return
        self._downloading = True
        t = threading.Thread(
            target=self._download_and_activate,
            daemon=True,
            name="bert-model-downloader",
        )
        t.start()

    def _download_and_activate(self) -> None:
        """
        Download the model from HuggingFace and save it locally.
        Runs in a daemon thread — never blocks the event loop.
        """
        try:
            from transformers import (  # type: ignore
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            os.makedirs(self._model_path, exist_ok=True)
            logger.info(
                "[bert] Downloading %s → %s (runs once, ~80 MB)...",
                _HF_MODEL_ID,
                self._model_path,
            )

            model = AutoModelForSequenceClassification.from_pretrained(_HF_MODEL_ID)
            tokenizer = AutoTokenizer.from_pretrained(_HF_MODEL_ID)

            model.save_pretrained(self._model_path)
            tokenizer.save_pretrained(self._model_path)

            logger.info("[bert] Download complete — activating BERT (hot-swap, no restart needed)")
            # Hot-swap: _load_model flips self._use_regex = False atomically.
            # Python's GIL makes this safe without an explicit lock.
            self._load_model()

        except Exception as exc:
            logger.warning(
                "[bert] Background download failed: %s — regex remains active. "
                "Check your internet connection or set TRANSFORMERS_OFFLINE=1 "
                "and place the model at %s manually.",
                exc,
                self._model_path,
            )
        finally:
            self._downloading = False
