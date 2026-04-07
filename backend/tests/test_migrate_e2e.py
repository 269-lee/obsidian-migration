"""
End-to-end test for /api/migrate with dummy data.
Tests the full SSE stream to verify progress events and catch the 35% hang issue.
"""
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app

# ── Dummy data ──────────────────────────────────────────────────────────────

DUMMY_NOTION_PAGES = [
    {
        "id": "page-001",
        "properties": {
            "title": {"title": [{"plain_text": "Project X 킥오프 회의"}]}
        },
        "created_time": "2024-03-01T10:00:00Z",
    },
    {
        "id": "page-002",
        "properties": {
            "title": {"title": [{"plain_text": "Q1 목표 설정"}]}
        },
        "created_time": "2024-01-10T09:00:00Z",
    },
]

DUMMY_NOTION_CONTENT = {
    "page-001": {
        "title": "Project X 킥오프 회의",
        "created_time": "2024-03-01T10:00:00Z",
        "blocks": [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "홍길동, 김철수 참석. Project X 1단계 계획 수립."}]}},
            {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "3월 말까지 프로토타입 완성"}]}},
            {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "디자인 시안 검토"}]}},
        ],
    },
    "page-002": {
        "title": "Q1 목표 설정",
        "created_time": "2024-01-10T09:00:00Z",
        "blocks": [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "2024년 1분기 팀 목표를 정리합니다."}]}},
            {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "핵심 목표"}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "MAU 20% 성장 및 Project X 런칭."}]}},
        ],
    },
}

DUMMY_SLACK_CHANNELS = [
    {"id": "C001", "name": "general"},
    {"id": "C002", "name": "project-x"},
]

DUMMY_SLACK_MESSAGES = {
    "C001": [
        {"user": "U001", "text": "오늘 미팅 어땠어요?", "ts": "1710000000.000001"},
        {"user": "U002", "text": "Project X 진행 잘 되고 있습니다!", "ts": "1710000060.000002"},
    ],
    "C002": [
        {"user": "U001", "text": "프로토타입 리뷰 일정 잡겠습니다", "ts": "1710001000.000001"},
        {"bot_id": "BOT1", "text": "자동화 알림", "ts": "1710001100.000002"},  # bot message (skipped)
    ],
}

DUMMY_SCHEMA = {
    "tags": ["project-x", "meeting", "Q1", "planning"],
    "people": ["홍길동", "김철수"],
    "projects": ["Project X"],
    "property_schema": {
        "required": ["title", "source", "date", "tags"],
        "optional": ["people", "project", "related", "status"],
    },
    "relationships": [
        {"from": "Project X 킥오프 회의", "to": "Q1 목표 설정", "reason": "같은 프로젝트 계획"},
        {"from": "Slack - C002", "to": "Project X 킥오프 회의", "reason": "Project X 관련 채널"},
    ],
}

DUMMY_CLASSIFIED = {
    "folder": "Projects",
    "frontmatter": {
        "title": "{title}",
        "source": "{source}",
        "date": "2024-03-01",
        "tags": ["project-x", "meeting"],
        "people": ["홍길동", "김철수"],
        "project": "Project X",
        "related": ["Q1 목표 설정"],
        "status": "active",
    },
    "content": "[[홍길동]], [[김철수]] 참석.\n\n[[Project X]] 킥오프 회의 내용 정리.",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_sse_stream(response) -> list[dict]:
    """SSE 스트림에서 이벤트 파싱"""
    events = []
    for line in response.iter_lines():
        line = line.decode() if isinstance(line, bytes) else line
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def make_classified(doc: dict) -> dict:
    result = json.loads(json.dumps(DUMMY_CLASSIFIED))
    result["frontmatter"]["title"] = doc["title"]
    result["frontmatter"]["source"] = doc["source"]
    return result


# ── Fixtures ─────────────────────────────────────────────────────────────────

def mock_notion_connector():
    connector = MagicMock()
    connector.list_pages.return_value = DUMMY_NOTION_PAGES
    connector.get_page_content.side_effect = lambda page_id: DUMMY_NOTION_CONTENT[page_id]
    return connector


def mock_slack_connector():
    connector = MagicMock()
    connector.list_channels.return_value = DUMMY_SLACK_CHANNELS
    connector.get_messages.side_effect = lambda channel_id: DUMMY_SLACK_MESSAGES.get(channel_id, [])
    return connector


def mock_analyzer():
    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(return_value=DUMMY_SCHEMA)
    return analyzer


def mock_classifier():
    classifier = MagicMock()
    classifier.classify = AsyncMock(side_effect=lambda doc, *args, **kwargs: make_classified(doc))
    classifier.to_markdown.side_effect = lambda classified: (
        "---\ntitle: {}\n---\n\n{}".format(
            classified["frontmatter"]["title"], classified["content"]
        )
    )
    return classifier


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestMigrateEndpoint:

    @pytest.fixture(autouse=True)
    def client(self):
        self.client = TestClient(app, raise_server_exceptions=True)

    def _run_migration(self, payload: dict):
        with (
            patch("main.NotionConnector", return_value=mock_notion_connector()),
            patch("main.SlackConnector", return_value=mock_slack_connector()),
            patch("main.KnowledgeAnalyzer", return_value=mock_analyzer()),
            patch("main.NoteClassifier", return_value=mock_classifier()),
        ):
            with self.client.stream("POST", "/api/migrate", json=payload) as response:
                assert response.status_code == 200
                events = []
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        try:
                            events.append(json.loads(line[6:]))
                        except json.JSONDecodeError:
                            pass
                return events

    # ── Notion only ────────────────────────────────────────────────────────

    def test_notion_only_produces_progress_events(self):
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
            "notion_token": "secret_dummy",
            "notion_page_ids": ["page-001", "page-002"],
        })

        types = [e["type"] for e in events]
        assert "progress" in types
        assert "file" in types
        assert "done" in types

    def test_notion_only_progress_reaches_100(self):
        """done 이벤트가 percent 100을 가져야 함 (progress 타입은 마지막 문서 변환 후 ~67%까지만 올라감)"""
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
            "notion_token": "secret_dummy",
            "notion_page_ids": ["page-001", "page-002"],
        })

        percents = [e.get("percent", 0) for e in events if e.get("type") == "progress"]
        print(f"\n[Progress sequence] {percents}")
        # progress 이벤트는 최대 ~97%까지만 올라가고, done 이벤트가 100%를 가짐
        done = next((e for e in events if e["type"] == "done"), None)
        assert done is not None, "done 이벤트 없음"
        assert done["percent"] == 100

    def test_notion_only_never_stalls_at_35(self):
        """35%에서 멈춰서 done 없이 끝나지 않아야 함"""
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
            "notion_token": "secret_dummy",
            "notion_page_ids": ["page-001", "page-002"],
        })

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1, f"done 이벤트가 없음. 전체 이벤트: {events}"

    def test_notion_only_file_count_matches_pages(self):
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
            "notion_token": "secret_dummy",
            "notion_page_ids": ["page-001", "page-002"],
        })

        file_events = [e for e in events if e["type"] == "file"]
        assert len(file_events) == 2, f"file 이벤트 수 불일치: {len(file_events)}"

    def test_file_events_have_path_and_content(self):
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
            "notion_token": "secret_dummy",
            "notion_page_ids": ["page-001"],
        })

        file_events = [e for e in events if e["type"] == "file"]
        for fe in file_events:
            assert "path" in fe, f"file 이벤트에 path 없음: {fe}"
            assert "content" in fe, f"file 이벤트에 content 없음: {fe}"
            assert fe["path"].endswith(".md"), f"path가 .md로 안 끝남: {fe['path']}"

    # ── Slack only ─────────────────────────────────────────────────────────

    def test_slack_only_produces_file_per_channel(self):
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
            "slack_token": "xoxb-dummy",
            "slack_channel_ids": ["C001", "C002"],
        })

        file_events = [e for e in events if e["type"] == "file"]
        assert len(file_events) == 2

    # ── Combined sources ───────────────────────────────────────────────────

    def test_combined_notion_and_slack(self):
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
            "notion_token": "secret_dummy",
            "notion_page_ids": ["page-001"],
            "slack_token": "xoxb-dummy",
            "slack_channel_ids": ["C001"],
        })

        file_events = [e for e in events if e["type"] == "file"]
        done_events = [e for e in events if e["type"] == "done"]
        assert len(file_events) == 2  # 1 notion + 1 slack
        assert done_events[0]["total"] == 2

    # ── Edge cases ─────────────────────────────────────────────────────────

    def test_no_sources_returns_error(self):
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
        })

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "없습니다" in error_events[0]["message"]

    def test_missing_api_key_returns_400(self):
        with (
            patch("main.NotionConnector", return_value=mock_notion_connector()),
            patch("main.KnowledgeAnalyzer", return_value=mock_analyzer()),
            patch("main.NoteClassifier", return_value=mock_classifier()),
        ):
            response = self.client.post("/api/migrate", json={
                "claude_api_key": "",
                "notion_token": "secret_dummy",
                "notion_page_ids": ["page-001"],
            })
            assert response.status_code == 400

    def test_sse_content_type(self):
        with (
            patch("main.NotionConnector", return_value=mock_notion_connector()),
            patch("main.KnowledgeAnalyzer", return_value=mock_analyzer()),
            patch("main.NoteClassifier", return_value=mock_classifier()),
        ):
            with self.client.stream("POST", "/api/migrate", json={
                "claude_api_key": "sk-ant-dummy",
                "notion_token": "secret_dummy",
                "notion_page_ids": ["page-001"],
            }) as response:
                assert "text/event-stream" in response.headers.get("content-type", "")

    def test_progress_order_is_monotonically_increasing(self):
        """progress percent가 앞으로만 진행해야 함"""
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
            "notion_token": "secret_dummy",
            "notion_page_ids": ["page-001", "page-002"],
            "slack_token": "xoxb-dummy",
            "slack_channel_ids": ["C001"],
        })

        percents = [e["percent"] for e in events if e.get("type") == "progress"]
        print(f"\n[Full progress] {percents}")
        for i in range(1, len(percents)):
            assert percents[i] >= percents[i - 1], (
                f"progress가 뒤로 감: {percents[i-1]} → {percents[i]}"
            )

    def test_done_event_has_correct_total(self):
        events = self._run_migration({
            "claude_api_key": "sk-ant-dummy",
            "notion_token": "secret_dummy",
            "notion_page_ids": ["page-001", "page-002"],
        })

        done = next(e for e in events if e["type"] == "done")
        assert done["total"] == 2
        assert done["percent"] == 100

