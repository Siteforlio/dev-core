from app.core.exceptions import (
    OverlaySessionNotFoundError,
    AudioCaptureError,
    BertClassifierError,
    LLMRateLimitedError,
    CodeRunnerError,
)


def test_overlay_session_not_found():
    e = OverlaySessionNotFoundError()
    assert e.code == "OVERLAY_SESSION_NOT_FOUND"
    assert e.status_code == 404


def test_bert_classifier_error_is_non_fatal():
    e = BertClassifierError()
    assert e.code == "BERT_UNAVAILABLE"
    assert e.status_code == 500


def test_code_runner_quota_exceeded():
    e = CodeRunnerError(code="CODE_RUNNER_QUOTA_EXCEEDED")
    assert e.code == "CODE_RUNNER_QUOTA_EXCEEDED"


def test_all_exceptions_inherit_devcore_exception():
    from app.core.exceptions import DevCoreException
    for cls in [OverlaySessionNotFoundError, AudioCaptureError,
                BertClassifierError, LLMRateLimitedError, CodeRunnerError]:
        assert issubclass(cls, DevCoreException)


def test_llm_rate_limited_status():
    e = LLMRateLimitedError()
    assert e.status_code == 429


def test_audio_capture_custom_message():
    e = AudioCaptureError("mic device not found")
    assert e.message == "mic device not found"
    assert e.status_code == 500
