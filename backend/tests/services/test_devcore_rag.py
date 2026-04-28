import pytest, tempfile, os
from app.services.cluely.rag_service import RagService

@pytest.mark.asyncio
async def test_build_and_retrieve(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("Redis is an in-memory data structure store used as a cache.")
    svc = RagService(index_dir=str(tmp_path / "index"))
    await svc.build_index([str(tmp_path)])
    chunks = await svc.retrieve("What is Redis?", k=1)
    assert len(chunks) == 1
    assert "Redis" in chunks[0]

@pytest.mark.asyncio
async def test_incremental_skips_unchanged(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("Python is a programming language.")
    svc = RagService(index_dir=str(tmp_path / "index"))
    await svc.build_index([str(tmp_path)])
    mtime_before = os.path.getmtime(str(tmp_path / "index" / "index_meta.json"))
    # No file changes — rebuild should not update meta
    await svc.build_index([str(tmp_path)])
    mtime_after = os.path.getmtime(str(tmp_path / "index" / "index_meta.json"))
    assert mtime_before == mtime_after
    # Verify index is still functional after no-op rebuild
    chunks = await svc.retrieve("programming language", k=1)
    assert "Python" in chunks[0]
