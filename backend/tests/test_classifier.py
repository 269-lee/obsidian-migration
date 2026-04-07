import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from ai.classifier import NoteClassifier


MOCK_CLASSIFIED = {
    "folder": "Projects",
    "frontmatter": {
        "title": "프로젝트 미팅",
        "source": "notion",
        "date": "2024-01-01",
        "tags": ["project-x", "meeting"],
        "people": ["[[홍길동]]"],
        "project": "[[Project X]]",
        "related": ["[[노트B]]"],
        "status": "active"
    },
    "content": "[[Project X]] 관련 미팅 내용입니다.\n[[홍길동]]이 참석했습니다."
}


@pytest.mark.asyncio
async def test_classify_returns_folder_and_frontmatter():
    with patch("ai.classifier.anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=MagicMock(
            content=[MagicMock(text=json.dumps(MOCK_CLASSIFIED))]
        ))

        classifier = NoteClassifier(api_key="test-key")
        doc = {"title": "프로젝트 미팅", "content": "내용", "source": "notion", "date": "2024-01-01"}
        schema = {"tags": ["project-x"], "people": ["홍길동"], "projects": ["Project X"]}
        result = await classifier.classify(doc, schema, ["노트A", "노트B"], ["Projects", "Areas"])

        assert result["folder"] == "Projects"
        assert "frontmatter" in result
        assert "content" in result
        assert "[[" in result["content"]


@pytest.mark.asyncio
async def test_classify_builds_markdown_file():
    with patch("ai.classifier.anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=MagicMock(
            content=[MagicMock(text=json.dumps(MOCK_CLASSIFIED))]
        ))

        classifier = NoteClassifier(api_key="test-key")
        doc = {"title": "프로젝트 미팅", "content": "내용", "source": "notion", "date": "2024-01-01"}
        schema = {"tags": [], "people": [], "projects": []}
        result = await classifier.classify(doc, schema, [], ["Projects"])
        md = classifier.to_markdown(result)

        assert md.startswith("---")
        assert "title:" in md
        assert "source:" in md
        assert "---" in md
