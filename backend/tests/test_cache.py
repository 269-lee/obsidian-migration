"""
캐시 파일 무결성 테스트
- cache_*.json 로드/저장/dedup key 고유성 검증
- CLAUDE.md 원칙: page_id 또는 고유한 식별자를 key로 사용해야 함
"""

import json
import os
import tempfile
import pytest
from pathlib import Path


BACKEND_DIR = Path(__file__).parent.parent
CACHE_FILES = {
    "chunks": BACKEND_DIR / "cache_chunks.json",
    "clusters": BACKEND_DIR / "cache_clusters.json",
    "notion": BACKEND_DIR / "cache_notion.json",
    "slack": BACKEND_DIR / "cache_slack.json",
    "synthesis": BACKEND_DIR / "cache_synthesis.json",
}


class TestCacheFileIntegrity:
    """실제 캐시 파일이 존재할 때 무결성 검사"""

    def test_cache_files_are_valid_json(self):
        """존재하는 캐시 파일이 유효한 JSON인지 검증"""
        for name, path in CACHE_FILES.items():
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        assert data is not None, f"{name} 캐시가 None입니다"
                    except json.JSONDecodeError as e:
                        pytest.fail(f"{name} 캐시 파일이 손상되었습니다: {e}")

    def test_notion_cache_has_unique_page_ids(self):
        """Notion 캐시의 page_id가 고유한지 검증 (중복 시 수백 문서가 하나로 처리)"""
        path = CACHE_FILES["notion"]
        if not path.exists():
            pytest.skip("cache_notion.json 없음")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            pytest.skip("Notion 캐시 형식이 리스트가 아님")

        page_ids = [doc.get("page_id") or doc.get("id") for doc in data if isinstance(doc, dict)]
        page_ids = [pid for pid in page_ids if pid]

        assert len(page_ids) == len(set(page_ids)), (
            f"Notion 캐시에 중복 page_id가 있습니다. "
            f"총 {len(page_ids)}개 중 고유값 {len(set(page_ids))}개"
        )

    def test_slack_cache_has_unique_thread_ids(self):
        """Slack 캐시의 thread_id가 고유한지 검증"""
        path = CACHE_FILES["slack"]
        if not path.exists():
            pytest.skip("cache_slack.json 없음")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            pytest.skip("Slack 캐시 형식이 리스트가 아님")

        thread_ids = [
            doc.get("thread_ts") or doc.get("ts") or doc.get("id")
            for doc in data
            if isinstance(doc, dict)
        ]
        thread_ids = [tid for tid in thread_ids if tid]

        assert len(thread_ids) == len(set(thread_ids)), (
            f"Slack 캐시에 중복 thread_id가 있습니다. "
            f"총 {len(thread_ids)}개 중 고유값 {len(set(thread_ids))}개"
        )

    def test_chunks_cache_structure(self):
        """chunks 캐시가 문서 단위 저장 구조인지 검증"""
        path = CACHE_FILES["chunks"]
        if not path.exists():
            pytest.skip("cache_chunks.json 없음")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        # chunks 캐시는 dict (doc_id → chunks 리스트) 형태여야 함
        assert isinstance(data, dict), "chunks 캐시는 dict 형태여야 합니다"
        for key, value in list(data.items())[:5]:
            assert key, "chunk 캐시 key가 비어있습니다"
            assert key != "Untitled", (
                f"chunk 캐시 key가 'Untitled'입니다. "
                "page_id 등 고유한 식별자를 사용해야 합니다 (CLAUDE.md 원칙)"
            )

    def test_synthesis_cache_has_content(self):
        """합성 캐시 각 항목에 내용이 있는지 검증"""
        path = CACHE_FILES["synthesis"]
        if not path.exists():
            pytest.skip("cache_synthesis.json 없음")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict), "synthesis 캐시는 dict 형태여야 합니다"
        for key, value in list(data.items())[:10]:
            assert value, f"synthesis 캐시 항목 '{key}'의 내용이 비어있습니다"


class TestCacheSaveLoad:
    """캐시 저장/로드 로직 단위 테스트"""

    def test_incremental_save_does_not_overwrite_existing(self):
        """증분 저장이 기존 데이터를 덮어쓰지 않는지 검증"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"doc_001": ["chunk1", "chunk2"]}, f)
            tmp_path = f.name

        try:
            # 기존 캐시 로드
            with open(tmp_path, encoding="utf-8") as f:
                cache = json.load(f)

            # 새 항목 추가
            cache["doc_002"] = ["chunk3"]

            # 저장
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

            # 검증: 기존 항목 보존
            with open(tmp_path, encoding="utf-8") as f:
                result = json.load(f)

            assert "doc_001" in result, "기존 캐시 항목이 사라졌습니다"
            assert "doc_002" in result, "새 캐시 항목이 저장되지 않았습니다"

        finally:
            os.unlink(tmp_path)

    def test_unique_key_prevents_duplicate_processing(self):
        """고유 key 사용 시 중복 처리 방지 검증"""
        cache = {}
        documents = [
            {"page_id": "abc123", "title": "Untitled"},
            {"page_id": "def456", "title": "Untitled"},  # 같은 제목, 다른 ID
        ]

        for doc in documents:
            key = doc["page_id"]  # page_id를 key로 사용
            if key not in cache:
                cache[key] = {"processed": True, "title": doc["title"]}

        assert len(cache) == 2, "page_id가 고유해서 2개 모두 처리되어야 합니다"

    def test_title_key_causes_duplicate_loss(self):
        """title을 key로 쓰면 중복 손실이 발생함을 시연 (잘못된 패턴)"""
        cache = {}
        documents = [
            {"page_id": "abc123", "title": "Untitled"},
            {"page_id": "def456", "title": "Untitled"},
        ]

        for doc in documents:
            key = doc["title"]  # ❌ title을 key로 사용하면 덮어씀
            cache[key] = {"processed": True, "page_id": doc["page_id"]}

        assert len(cache) == 1, "title key를 쓰면 중복으로 1개만 남습니다 (두 번째가 첫 번째를 덮어씀)"
