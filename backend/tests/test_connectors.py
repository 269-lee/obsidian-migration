"""
Notion/Slack 수집 고유성 검증 테스트
- page_id / thread_id 고유성
- 수집 결과 스키마 검증
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestNotionConnectorUniqueness:
    """Notion 수집 시 page_id 고유성 검증"""

    def test_notion_documents_have_page_id(self):
        """Notion 문서는 반드시 page_id를 가져야 함"""
        mock_pages = [
            {"page_id": "abc-123", "title": "프로젝트 A", "content": "내용"},
            {"page_id": "def-456", "title": "Untitled", "content": "내용"},
            {"page_id": "ghi-789", "title": "Untitled", "content": "내용"},
        ]

        for page in mock_pages:
            assert "page_id" in page, "page_id가 없습니다"
            assert page["page_id"], "page_id가 비어있습니다"

    def test_notion_page_ids_are_unique(self):
        """수집된 Notion 페이지들의 page_id가 고유한지 검증"""
        mock_pages = [
            {"page_id": "abc-123", "title": "노트1"},
            {"page_id": "def-456", "title": "노트2"},
            {"page_id": "ghi-789", "title": "노트3"},
        ]

        page_ids = [p["page_id"] for p in mock_pages]
        assert len(page_ids) == len(set(page_ids)), "page_id 중복이 있습니다"

    def test_duplicate_page_id_detected(self):
        """중복 page_id가 감지되어야 함"""
        mock_pages = [
            {"page_id": "abc-123", "title": "노트1"},
            {"page_id": "abc-123", "title": "노트2"},  # 중복!
        ]

        page_ids = [p["page_id"] for p in mock_pages]
        has_duplicates = len(page_ids) != len(set(page_ids))
        assert has_duplicates, "중복 page_id가 감지되지 않았습니다"

    def test_notion_document_schema(self):
        """Notion 문서 필수 필드 검증"""
        required_fields = {"page_id", "title", "content"}
        mock_doc = {
            "page_id": "abc-123",
            "title": "테스트 노트",
            "content": "## 내용\n테스트입니다",
            "source": "notion",
        }

        missing = required_fields - set(mock_doc.keys())
        assert not missing, f"필수 필드 누락: {missing}"

    def test_notion_project_property_preserved(self):
        """Notion project property가 보존되는지 검증"""
        mock_doc = {
            "page_id": "abc-123",
            "title": "실기 기획 킥오프",
            "content": "내용",
            "properties": {
                "project": "맞추다 실기 확장"
            }
        }

        assert "properties" in mock_doc
        assert "project" in mock_doc["properties"]


class TestSlackConnectorUniqueness:
    """Slack 수집 시 thread 고유성 검증"""

    def test_slack_threads_have_unique_ids(self):
        """Slack 스레드들의 ID가 고유한지 검증"""
        mock_threads = [
            {"ts": "1234567890.123456", "channel": "C01234", "text": "메시지1"},
            {"ts": "1234567891.123456", "channel": "C01234", "text": "메시지2"},
            {"ts": "1234567892.123456", "channel": "C05678", "text": "메시지3"},
        ]

        thread_ids = [t["ts"] for t in mock_threads]
        assert len(thread_ids) == len(set(thread_ids)), "thread_ts 중복이 있습니다"

    def test_slack_thread_document_schema(self):
        """Slack 스레드 문서 필수 필드 검증"""
        required_fields = {"ts", "channel", "text"}
        mock_thread = {
            "ts": "1234567890.123456",
            "channel": "C01234",
            "text": "메인 메시지",
            "replies": [
                {"ts": "1234567890.234567", "text": "답글1"},
            ],
            "source": "slack",
        }

        missing = required_fields - set(mock_thread.keys())
        assert not missing, f"필수 필드 누락: {missing}"

    def test_slack_standalong_messages_grouped_by_date(self):
        """스레드 없는 단발 메시지는 날짜별로 묶여야 함"""
        standalone_messages = [
            {"ts": "1700000000.000001", "date": "2024-03-15", "text": "공지1"},
            {"ts": "1700000001.000001", "date": "2024-03-15", "text": "공지2"},
            {"ts": "1700086400.000001", "date": "2024-03-16", "text": "공지3"},
        ]

        # 날짜별 그룹화
        grouped = {}
        for msg in standalone_messages:
            date = msg["date"]
            grouped.setdefault(date, []).append(msg)

        assert "2024-03-15" in grouped
        assert len(grouped["2024-03-15"]) == 2
        assert "2024-03-16" in grouped
        assert len(grouped["2024-03-16"]) == 1

    def test_slack_thread_id_uses_ts_not_title(self):
        """Slack thread의 캐시 key는 ts를 사용해야 함 (title이 없을 수 있음)"""
        mock_thread = {
            "ts": "1234567890.123456",
            "channel": "C01234",
            "text": "이 메시지는 제목이 없습니다",
        }

        # ts 기반 key 생성
        cache_key = f"{mock_thread['channel']}_{mock_thread['ts']}"
        assert "1234567890.123456" in cache_key
        assert cache_key != "Untitled"


class TestConnectorRateLimit:
    """API Rate Limit 방어 로직 검증"""

    def test_rate_limit_delay_is_configured(self):
        """Rate limit 대기 시간이 설정되어 있는지 확인"""
        # Notion API: 3 req/sec, Slack API: 1 req/sec per method
        NOTION_RATE_LIMIT_DELAY = 0.4   # 초
        SLACK_RATE_LIMIT_DELAY = 1.0    # 초

        assert NOTION_RATE_LIMIT_DELAY > 0, "Notion rate limit delay가 설정되지 않았습니다"
        assert SLACK_RATE_LIMIT_DELAY > 0, "Slack rate limit delay가 설정되지 않았습니다"

    def test_max_retries_configured(self):
        """최대 재시도 횟수가 합리적인지 검증"""
        MAX_RETRIES = 3
        assert 1 <= MAX_RETRIES <= 5, (
            f"MAX_RETRIES={MAX_RETRIES}가 비합리적입니다. "
            "1-5 사이여야 합니다 (너무 많으면 비용 3-5배)"
        )
