# backend/tests/services/test_email_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.email_service import EmailService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db

async def test_classify_interview(mock_db):
    service = EmailService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="interview")):
        result = await service.classify_email("Interview Invitation - Software Engineer", "We'd like to invite you...")
    assert result == "interview"

async def test_classify_rejection(mock_db):
    service = EmailService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="rejection")):
        result = await service.classify_email("Update on your application", "We regret to inform you...")
    assert result == "rejection"

async def test_decrypt_credentials_roundtrip(mock_db):
    service = EmailService(mock_db)
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    with patch("app.services.job_hunter.email_service.settings") as mock_settings:
        mock_settings.job_hunter_encryption_key = key.decode()
        encrypted = service.encrypt_credentials({"host": "imap.gmail.com", "password": "secret"})
        decrypted = service.decrypt_credentials(encrypted)
    assert decrypted["password"] == "secret"

async def test_generate_rejection_reply_is_professional(mock_db):
    service = EmailService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="Thank you for your consideration...")):
        reply = await service.generate_rejection_reply("Google", "Software Engineer")
    assert isinstance(reply, str)
    assert len(reply) > 20
