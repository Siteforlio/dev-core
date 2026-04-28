import asyncio
import os
import re
import logging
from app.core.exceptions import BertClassifierError

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = os.path.expanduser("~/.devcore/models/question-classifier")

_QUESTION_RE = re.compile(
    r'\b(what|who|where|when|why|how|which|whose|whom|can you|could you|'
    r'would you|tell me|explain|describe|have you|do you|are you|is there)\b',
    re.IGNORECASE,
)


def _regex_is_question(text: str) -> bool:
    """Heuristic fallback: question mark OR interrogative opener."""
    return text.strip().endswith('?') or bool(_QUESTION_RE.match(text.strip()))


class BertClassifier:
    def __init__(self, model_path: str = _DEFAULT_MODEL_PATH):
        self._use_regex = False
        self._pipe = None
        if not os.path.exists(model_path):
            logger.warning(
                "Question-classifier model not found at %s — using regex heuristic. "
                "Place a fine-tuned distilbert question-classification model there to enable BERT.",
                model_path,
            )
            self._use_regex = True
            return
        try:
            from transformers import pipeline
            self._pipe = pipeline(
                "text-classification",
                model=model_path,
                device=-1,
                truncation=True,
                max_length=128,
            )
            logger.info("BertClassifier loaded: %s", model_path)
        except Exception as e:
            raise BertClassifierError() from e

    async def is_question(self, text: str) -> bool:
        """Returns True if text is a question. Falls back to regex when model absent."""
        if self._use_regex:
            return _regex_is_question(text)

        def _run():
            results = self._pipe(text)
            return results[0]["label"] == "QUESTION"

        return await asyncio.to_thread(_run)
