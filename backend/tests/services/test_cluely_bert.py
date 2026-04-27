import pytest
from unittest.mock import patch, MagicMock
from app.services.cluely.bert_classifier import BertClassifier
from app.core.exceptions import BertClassifierError

@pytest.mark.asyncio
async def test_classifies_question_as_true():
    clf = BertClassifier()
    # force BERT mode (bypass regex fallback)
    clf._use_regex = False
    clf._pipe = MagicMock(return_value=[{'label': 'QUESTION', 'score': 0.95}])
    result = await clf.is_question("Tell me about your experience with distributed systems?")
    assert result is True

@pytest.mark.asyncio
async def test_classifies_statement_as_false():
    clf = BertClassifier()
    clf._use_regex = False
    clf._pipe = MagicMock(return_value=[{'label': 'STATEMENT', 'score': 0.88}])
    result = await clf.is_question("Tell me about yourself.")
    assert result is False

def test_falls_back_to_regex_on_missing_model():
    with patch('app.services.cluely.bert_classifier.os.path.exists', return_value=False):
        clf = BertClassifier(model_path="/nonexistent/model")
        assert clf._use_regex is True

@pytest.mark.asyncio
async def test_regex_fallback_detects_question():
    with patch('app.services.cluely.bert_classifier.os.path.exists', return_value=False):
        clf = BertClassifier(model_path="/nonexistent/model")
        assert await clf.is_question("Tell me about your distributed systems experience?") is True
        assert await clf.is_question("I worked at Google for three years.") is False
