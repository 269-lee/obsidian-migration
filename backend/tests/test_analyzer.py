import pytest
import json
from unittest.mock import MagicMock, patch
from ai.analyzer import KnowledgeAnalyzer


MOCK_SCHEMA = {
    "tags": ["project-x", "design"],
    "people": ["홍길동"],
    "projects": ["Project X"],
    "property_schema": {
        "required": ["title", "source", "date", "tags"],
        "optional": ["people", "project", "related", "status"]
    },
    "relationships": [
        {"from": "노트A", "to": "노트B", "reason": "같은 프로젝트"}
    ]
}


def test_analyze_returns_schema():
    with patch("ai.analyzer.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps(MOCK_SCHEMA))]
        )

        analyzer = KnowledgeAnalyzer(api_key="test-key")
        documents = [
            {"title": "노트A", "content": "Project X 관련 내용", "source": "notion"},
            {"title": "노트B", "content": "홍길동과 미팅", "source": "slack"},
        ]
        result = analyzer.analyze(documents, ["Projects", "Areas", "Resources", "Inbox"])

        assert "tags" in result
        assert "people" in result
        assert "projects" in result
        assert "relationships" in result


def test_analyze_calls_claude_with_documents():
    with patch("ai.analyzer.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps(MOCK_SCHEMA))]
        )

        analyzer = KnowledgeAnalyzer(api_key="test-key")
        documents = [{"title": "테스트", "content": "내용", "source": "notion"}]
        analyzer.analyze(documents, ["Projects"])

        assert mock_client.messages.create.called
        call_args = mock_client.messages.create.call_args
        user_message = call_args.kwargs["messages"][0]["content"]
        assert "테스트" in user_message
