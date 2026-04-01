# Obsidian Migration Solution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notion, Slack, Google Workspace 데이터를 수집해 Claude가 지식 그래프로 구조화하고, Obsidian vault에 wikilink + frontmatter가 있는 .md 파일로 저장하는 웹 서비스 구축

**Architecture:** Next.js 프론트엔드가 OAuth/UI를 담당하고, FastAPI 백엔드가 각 툴 API 수집 + Claude 분석 + SSE 스트리밍을 담당. 사용자 데이터는 백엔드에 저장되지 않고 File System Access API로 vault에 직접 기록.

**Tech Stack:** Python 3.11+, FastAPI, httpx, anthropic SDK, Next.js 14 (App Router), TypeScript, Tailwind CSS

---

## 파일 구조

```
obsidian-migration/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── notion.py
│   │   ├── slack.py
│   │   └── google.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── analyzer.py
│   │   └── classifier.py
│   ├── converter/
│   │   ├── __init__.py
│   │   └── markdown.py
│   └── tests/
│       ├── test_markdown.py
│       ├── test_notion.py
│       ├── test_slack.py
│       ├── test_google.py
│       ├── test_analyzer.py
│       └── test_classifier.py
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── next.config.ts
    ├── .env.local.example
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx           # OAuth 연결
    │   ├── select/page.tsx    # 소스 선택
    │   ├── structure/page.tsx # 폴더 구조 편집
    │   └── migrate/page.tsx   # 마이그레이션 실행
    ├── components/
    │   ├── SourceSelector.tsx
    │   ├── FolderEditor.tsx
    │   └── MigrationProgress.tsx
    └── lib/
        ├── types.ts
        ├── api.ts
        └── filesystem.ts
```

---

## Task 1: 백엔드 프로젝트 셋업

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/connectors/__init__.py`
- Create: `backend/ai/__init__.py`
- Create: `backend/converter/__init__.py`

- [ ] **Step 1: 백엔드 디렉토리 생성 및 의존성 파일 작성**

```bash
mkdir -p backend/connectors backend/ai backend/converter backend/tests
touch backend/connectors/__init__.py backend/ai/__init__.py backend/converter/__init__.py backend/tests/__init__.py
```

`backend/requirements.txt`:
```
fastapi==0.115.0
uvicorn==0.30.6
httpx==0.27.2
anthropic==0.34.2
google-api-python-client==2.147.0
google-auth-oauthlib==1.2.1
google-auth-httplib2==0.2.0
python-dotenv==1.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
respx==0.21.1
```

- [ ] **Step 2: 환경변수 예시 파일 작성**

`backend/.env.example`:
```
ANTHROPIC_API_KEY=sk-ant-...
NOTION_CLIENT_ID=...
NOTION_CLIENT_SECRET=...
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
FRONTEND_URL=http://localhost:3000
```

- [ ] **Step 3: 의존성 설치**

```bash
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
```

- [ ] **Step 4: 설치 확인**

```bash
python -c "import fastapi, anthropic, httpx; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: 커밋**

```bash
git add backend/
git commit -m "chore: initialize backend project structure"
```

---

## Task 2: Markdown 변환기

**Files:**
- Create: `backend/converter/markdown.py`
- Create: `backend/tests/test_markdown.py`

- [ ] **Step 1: 테스트 작성**

`backend/tests/test_markdown.py`:
```python
import pytest
from converter.markdown import (
    rich_text_to_str,
    notion_blocks_to_markdown,
    slack_messages_to_markdown,
)


def test_rich_text_to_str_plain():
    rich_text = [{"plain_text": "Hello"}, {"plain_text": " World"}]
    assert rich_text_to_str(rich_text) == "Hello World"


def test_rich_text_to_str_empty():
    assert rich_text_to_str([]) == ""


def test_notion_paragraph():
    blocks = [{
        "type": "paragraph",
        "paragraph": {"rich_text": [{"plain_text": "Hello World"}]}
    }]
    result = notion_blocks_to_markdown(blocks)
    assert "Hello World" in result


def test_notion_heading1():
    blocks = [{
        "type": "heading_1",
        "heading_1": {"rich_text": [{"plain_text": "Title"}]}
    }]
    result = notion_blocks_to_markdown(blocks)
    assert "# Title" in result


def test_notion_heading2():
    blocks = [{
        "type": "heading_2",
        "heading_2": {"rich_text": [{"plain_text": "Section"}]}
    }]
    assert "## Section" in notion_blocks_to_markdown(blocks)


def test_notion_bulleted_list():
    blocks = [{
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [{"plain_text": "Item"}]}
    }]
    assert "- Item" in notion_blocks_to_markdown(blocks)


def test_notion_code_block():
    blocks = [{
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": "print('hi')"}],
            "language": "python"
        }
    }]
    result = notion_blocks_to_markdown(blocks)
    assert "```python" in result
    assert "print('hi')" in result


def test_slack_messages_to_markdown():
    messages = [
        {"ts": "1700000000.000001", "user": "U123", "text": "Hello"},
        {"ts": "1700000001.000001", "user": "U456", "text": "World"},
    ]
    result = slack_messages_to_markdown(messages, channel_name="general")
    assert "# #general" in result
    assert "Hello" in result
    assert "World" in result


def test_slack_skips_bot_messages():
    messages = [
        {"ts": "1700000000.000001", "user": "U123", "text": "Human"},
        {"ts": "1700000001.000001", "bot_id": "B123", "text": "Bot message"},
    ]
    result = slack_messages_to_markdown(messages, channel_name="general")
    assert "Human" in result
    assert "Bot message" not in result
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd backend
pytest tests/test_markdown.py -v
```
Expected: `ModuleNotFoundError: No module named 'converter.markdown'`

- [ ] **Step 3: 구현**

`backend/converter/markdown.py`:
```python
from datetime import datetime


def rich_text_to_str(rich_text: list[dict]) -> str:
    return "".join(item["plain_text"] for item in rich_text)


def notion_blocks_to_markdown(blocks: list[dict]) -> str:
    lines = []
    for block in blocks:
        block_type = block["type"]
        content = block.get(block_type, {})
        rich_text = content.get("rich_text", [])
        text = rich_text_to_str(rich_text)

        if block_type == "paragraph":
            lines.append(text)
        elif block_type == "heading_1":
            lines.append(f"# {text}")
        elif block_type == "heading_2":
            lines.append(f"## {text}")
        elif block_type == "heading_3":
            lines.append(f"### {text}")
        elif block_type == "bulleted_list_item":
            lines.append(f"- {text}")
        elif block_type == "numbered_list_item":
            lines.append(f"1. {text}")
        elif block_type == "quote":
            lines.append(f"> {text}")
        elif block_type == "divider":
            lines.append("---")
        elif block_type == "code":
            lang = content.get("language", "")
            lines.append(f"```{lang}\n{text}\n```")
        else:
            if text:
                lines.append(text)

        lines.append("")
    return "\n".join(lines).strip()


def slack_messages_to_markdown(messages: list[dict], channel_name: str) -> str:
    lines = [f"# #{channel_name}", ""]
    for msg in messages:
        if "bot_id" in msg:
            continue
        ts = msg.get("ts", "")
        try:
            dt = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError):
            dt = ts
        user = msg.get("user", "unknown")
        text = msg.get("text", "")
        lines.append(f"**{user}** ({dt})")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def google_doc_to_markdown(doc: dict) -> str:
    lines = []
    title = doc.get("title", "Untitled")
    lines.append(f"# {title}")
    lines.append("")

    body = doc.get("body", {})
    for element in body.get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue

        style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        text_parts = []
        for pe in paragraph.get("elements", []):
            tr = pe.get("textRun")
            if tr:
                text_parts.append(tr.get("content", ""))
        text = "".join(text_parts).rstrip("\n")

        if not text.strip():
            lines.append("")
            continue

        if style == "HEADING_1":
            lines.append(f"# {text}")
        elif style == "HEADING_2":
            lines.append(f"## {text}")
        elif style == "HEADING_3":
            lines.append(f"### {text}")
        else:
            lines.append(text)

    return "\n".join(lines)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd backend
pytest tests/test_markdown.py -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/converter/ backend/tests/test_markdown.py
git commit -m "feat: add markdown converter for Notion, Slack, Google Docs"
```

---

## Task 3: Notion 커넥터

**Files:**
- Create: `backend/connectors/notion.py`
- Create: `backend/tests/test_notion.py`

- [ ] **Step 1: 테스트 작성**

`backend/tests/test_notion.py`:
```python
import pytest
import respx
import httpx
from connectors.notion import NotionConnector


BASE_URL = "https://api.notion.com/v1"


@pytest.fixture
def connector():
    return NotionConnector(token="test-token")


@respx.mock
def test_list_pages(connector):
    respx.post(f"{BASE_URL}/search").mock(return_value=httpx.Response(200, json={
        "results": [
            {"id": "page-1", "properties": {"title": {"title": [{"plain_text": "Page 1"}]}}},
            {"id": "page-2", "properties": {"title": {"title": [{"plain_text": "Page 2"}]}}},
        ]
    }))
    pages = connector.list_pages()
    assert len(pages) == 2
    assert pages[0]["id"] == "page-1"


@respx.mock
def test_get_page_content(connector):
    page_id = "abc123"
    respx.get(f"{BASE_URL}/pages/{page_id}").mock(return_value=httpx.Response(200, json={
        "id": page_id,
        "properties": {"title": {"title": [{"plain_text": "My Page"}]}},
        "created_time": "2024-01-01T00:00:00Z",
    }))
    respx.get(f"{BASE_URL}/blocks/{page_id}/children").mock(return_value=httpx.Response(200, json={
        "results": [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello"}]}}
        ]
    }))
    content = connector.get_page_content(page_id)
    assert content["title"] == "My Page"
    assert len(content["blocks"]) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_notion.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`backend/connectors/notion.py`:
```python
import httpx


class NotionConnector:
    BASE_URL = "https://api.notion.com/v1"

    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    def list_pages(self) -> list[dict]:
        with httpx.Client() as client:
            response = client.post(
                f"{self.BASE_URL}/search",
                headers=self.headers,
                json={"filter": {"value": "page", "property": "object"}, "page_size": 100},
            )
            response.raise_for_status()
            return response.json()["results"]

    def get_page_content(self, page_id: str) -> dict:
        with httpx.Client() as client:
            page_resp = client.get(
                f"{self.BASE_URL}/pages/{page_id}", headers=self.headers
            )
            page_resp.raise_for_status()
            page = page_resp.json()

            blocks_resp = client.get(
                f"{self.BASE_URL}/blocks/{page_id}/children", headers=self.headers
            )
            blocks_resp.raise_for_status()

            title_prop = page.get("properties", {}).get("title", {})
            title_parts = title_prop.get("title", [])
            title = "".join(t["plain_text"] for t in title_parts) or "Untitled"

            return {
                "id": page_id,
                "title": title,
                "created_time": page.get("created_time", ""),
                "blocks": blocks_resp.json()["results"],
            }
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_notion.py -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/connectors/notion.py backend/tests/test_notion.py
git commit -m "feat: add Notion connector"
```

---

## Task 4: Slack 커넥터

**Files:**
- Create: `backend/connectors/slack.py`
- Create: `backend/tests/test_slack.py`

- [ ] **Step 1: 테스트 작성**

`backend/tests/test_slack.py`:
```python
import pytest
import respx
import httpx
from connectors.slack import SlackConnector


BASE_URL = "https://slack.com/api"


@pytest.fixture
def connector():
    return SlackConnector(token="xoxb-test")


@respx.mock
def test_list_channels(connector):
    respx.get(f"{BASE_URL}/conversations.list").mock(return_value=httpx.Response(200, json={
        "ok": True,
        "channels": [
            {"id": "C001", "name": "general"},
            {"id": "C002", "name": "random"},
        ]
    }))
    channels = connector.list_channels()
    assert len(channels) == 2
    assert channels[0]["name"] == "general"


@respx.mock
def test_get_messages(connector):
    respx.get(f"{BASE_URL}/conversations.history").mock(return_value=httpx.Response(200, json={
        "ok": True,
        "messages": [
            {"ts": "1700000000.000001", "user": "U123", "text": "Hello"},
        ]
    }))
    messages = connector.get_messages("C001")
    assert len(messages) == 1
    assert messages[0]["text"] == "Hello"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_slack.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`backend/connectors/slack.py`:
```python
import httpx


class SlackConnector:
    BASE_URL = "https://slack.com/api"

    def __init__(self, token: str):
        self.headers = {"Authorization": f"Bearer {token}"}

    def list_channels(self) -> list[dict]:
        with httpx.Client() as client:
            response = client.get(
                f"{self.BASE_URL}/conversations.list",
                headers=self.headers,
                params={"types": "public_channel,private_channel", "limit": 200},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("channels", [])

    def get_messages(self, channel_id: str) -> list[dict]:
        with httpx.Client() as client:
            response = client.get(
                f"{self.BASE_URL}/conversations.history",
                headers=self.headers,
                params={"channel": channel_id, "limit": 1000},
            )
            response.raise_for_status()
            return response.json().get("messages", [])
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_slack.py -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/connectors/slack.py backend/tests/test_slack.py
git commit -m "feat: add Slack connector"
```

---

## Task 5: Google 커넥터

**Files:**
- Create: `backend/connectors/google.py`
- Create: `backend/tests/test_google.py`

- [ ] **Step 1: 테스트 작성**

`backend/tests/test_google.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from connectors.google import GoogleConnector


@pytest.fixture
def mock_creds():
    return {
        "access_token": "test-token",
        "refresh_token": "refresh",
        "client_id": "client-id",
        "client_secret": "client-secret",
    }


def test_list_docs(mock_creds):
    with patch("connectors.google.build") as mock_build:
        mock_drive = MagicMock()
        mock_drive.files().list().execute.return_value = {
            "files": [
                {"id": "doc1", "name": "Meeting Notes", "modifiedTime": "2024-01-01T00:00:00Z"},
            ]
        }
        mock_build.return_value = mock_drive

        connector = GoogleConnector(mock_creds)
        connector.drive = mock_drive
        docs = connector.list_docs()
        assert len(docs) == 1
        assert docs[0]["name"] == "Meeting Notes"


def test_get_doc(mock_creds):
    with patch("connectors.google.build"):
        connector = GoogleConnector(mock_creds)
        mock_docs = MagicMock()
        mock_docs.documents().get().execute.return_value = {
            "documentId": "doc1",
            "title": "Meeting Notes",
            "body": {"content": []},
        }
        connector.docs = mock_docs
        doc = connector.get_doc("doc1")
        assert doc["title"] == "Meeting Notes"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_google.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`backend/connectors/google.py`:
```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GoogleConnector:
    def __init__(self, credentials: dict):
        creds = Credentials(
            token=credentials["access_token"],
            refresh_token=credentials.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
        )
        self.drive = build("drive", "v3", credentials=creds)
        self.docs = build("docs", "v1", credentials=creds)

    def list_docs(self) -> list[dict]:
        results = self.drive.files().list(
            q="mimeType='application/vnd.google-apps.document' and trashed=false",
            fields="files(id, name, modifiedTime)",
            pageSize=200,
        ).execute()
        return results.get("files", [])

    def get_doc(self, doc_id: str) -> dict:
        return self.docs.documents().get(documentId=doc_id).execute()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_google.py -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/connectors/google.py backend/tests/test_google.py
git commit -m "feat: add Google connector"
```

---

## Task 6: Claude 분석기 (1단계)

**Files:**
- Create: `backend/ai/analyzer.py`
- Create: `backend/tests/test_analyzer.py`

- [ ] **Step 1: 테스트 작성**

`backend/tests/test_analyzer.py`:
```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_analyzer.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`backend/ai/analyzer.py`:
```python
import json
import anthropic


class KnowledgeAnalyzer:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, documents: list[dict], folder_structure: list[str]) -> dict:
        doc_summaries = "\n\n".join(
            f"[{d['source']}] 제목: {d['title']}\n내용: {d['content'][:800]}"
            for d in documents
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""다음은 마이그레이션할 문서들입니다:

{doc_summaries}

폴더 구조: {', '.join(folder_structure)}

이 문서들을 분석하여 Obsidian 지식 그래프를 위한 스키마를 설계해주세요.
반드시 아래 JSON 형식으로만 응답하세요:

{{
  "tags": ["자주 등장하는 핵심 태그 목록"],
  "people": ["언급된 사람 이름 목록"],
  "projects": ["식별된 프로젝트/주제 목록"],
  "property_schema": {{
    "required": ["title", "source", "date", "tags"],
    "optional": ["people", "project", "related", "status"]
  }},
  "relationships": [
    {{"from": "문서제목", "to": "문서제목", "reason": "연관 이유"}}
  ]
}}"""
            }]
        )

        return json.loads(response.content[0].text)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_analyzer.py -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/ai/analyzer.py backend/tests/test_analyzer.py
git commit -m "feat: add Claude knowledge analyzer (1st pass)"
```

---

## Task 7: Claude 분류기 (2단계)

**Files:**
- Create: `backend/ai/classifier.py`
- Create: `backend/tests/test_classifier.py`

- [ ] **Step 1: 테스트 작성**

`backend/tests/test_classifier.py`:
```python
import pytest
import json
from unittest.mock import MagicMock, patch
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


def test_classify_returns_folder_and_frontmatter():
    with patch("ai.classifier.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps(MOCK_CLASSIFIED))]
        )

        classifier = NoteClassifier(api_key="test-key")
        doc = {"title": "프로젝트 미팅", "content": "내용", "source": "notion", "date": "2024-01-01"}
        schema = {"tags": ["project-x"], "people": ["홍길동"], "projects": ["Project X"]}
        result = classifier.classify(doc, schema, ["노트A", "노트B"], ["Projects", "Areas"])

        assert result["folder"] == "Projects"
        assert "frontmatter" in result
        assert "content" in result
        assert "[[" in result["content"]


def test_classify_builds_markdown_file():
    with patch("ai.classifier.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps(MOCK_CLASSIFIED))]
        )

        classifier = NoteClassifier(api_key="test-key")
        doc = {"title": "프로젝트 미팅", "content": "내용", "source": "notion", "date": "2024-01-01"}
        schema = {"tags": [], "people": [], "projects": []}
        result = classifier.classify(doc, schema, [], ["Projects"])
        md = classifier.to_markdown(result)

        assert md.startswith("---")
        assert "title:" in md
        assert "source:" in md
        assert "---" in md
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_classifier.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`backend/ai/classifier.py`:
```python
import json
import anthropic


class NoteClassifier:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def classify(
        self,
        document: dict,
        schema: dict,
        all_titles: list[str],
        folder_structure: list[str],
    ) -> dict:
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            messages=[{
                "role": "user",
                "content": f"""다음 문서를 Obsidian 노트로 변환하세요.

제목: {document['title']}
출처: {document['source']}
날짜: {document.get('date', '')}
내용:
{document['content']}

사용 가능한 폴더: {', '.join(folder_structure)}
알려진 태그: {', '.join(schema.get('tags', []))}
알려진 사람: {', '.join(schema.get('people', []))}
알려진 프로젝트: {', '.join(schema.get('projects', []))}
전체 노트 제목 (wikilink 대상): {', '.join(all_titles)}

지시사항:
- 내용에서 관련 노트를 발견하면 [[노트제목]] 형태로 wikilink를 삽입하세요
- 사람 이름, 프로젝트명은 [[이름]] 형태로 링크하세요
- 반드시 아래 JSON으로만 응답하세요:

{{
  "folder": "폴더명",
  "frontmatter": {{
    "title": "...",
    "source": "notion|slack|google",
    "date": "YYYY-MM-DD",
    "tags": [],
    "people": [],
    "project": "",
    "related": [],
    "status": "active"
  }},
  "content": "[[wikilink]]이 포함된 마크다운 본문"
}}"""
            }]
        )
        return json.loads(response.content[0].text)

    def to_markdown(self, classified: dict) -> str:
        fm = classified["frontmatter"]
        lines = ["---"]
        for key, value in fm.items():
            if isinstance(value, list):
                if value:
                    lines.append(f"{key}:")
                    for item in value:
                        lines.append(f"  - {item}")
                else:
                    lines.append(f"{key}: []")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")
        lines.append(classified["content"])
        return "\n".join(lines)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_classifier.py -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/ai/classifier.py backend/tests/test_classifier.py
git commit -m "feat: add Claude note classifier with wikilink generation (2nd pass)"
```

---

## Task 8: FastAPI 메인 앱 + SSE 엔드포인트

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: main.py 작성**

`backend/main.py`:
```python
import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from connectors.notion import NotionConnector
from connectors.slack import SlackConnector
from connectors.google import GoogleConnector
from converter.markdown import notion_blocks_to_markdown, slack_messages_to_markdown, google_doc_to_markdown
from ai.analyzer import KnowledgeAnalyzer
from ai.classifier import NoteClassifier

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SourceSelection(BaseModel):
    notion_token: str | None = None
    notion_page_ids: list[str] = []
    slack_token: str | None = None
    slack_channel_ids: list[str] = []
    google_credentials: dict | None = None
    google_doc_ids: list[str] = []
    folder_structure: list[str] = ["Projects", "Areas", "Resources", "Inbox"]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/sources/notion/pages")
def list_notion_pages(body: dict):
    connector = NotionConnector(token=body["token"])
    pages = connector.list_pages()
    return [
        {
            "id": p["id"],
            "title": "".join(
                t["plain_text"]
                for t in p.get("properties", {}).get("title", {}).get("title", [])
            ) or "Untitled"
        }
        for p in pages
    ]


@app.post("/api/sources/slack/channels")
def list_slack_channels(body: dict):
    connector = SlackConnector(token=body["token"])
    channels = connector.list_channels()
    return [{"id": c["id"], "name": c["name"]} for c in channels]


@app.post("/api/sources/google/docs")
def list_google_docs(body: dict):
    connector = GoogleConnector(credentials=body["credentials"])
    docs = connector.list_docs()
    return [{"id": d["id"], "name": d["name"]} for d in docs]


@app.post("/api/migrate")
def migrate(selection: SourceSelection):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    def generate():
        documents = []

        # Notion 수집
        if selection.notion_token and selection.notion_page_ids:
            connector = NotionConnector(token=selection.notion_token)
            for i, page_id in enumerate(selection.notion_page_ids):
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Notion 페이지 수집 중... ({i+1}/{len(selection.notion_page_ids)})', 'percent': 5})}\n\n"
                content = connector.get_page_content(page_id)
                markdown = notion_blocks_to_markdown(content["blocks"])
                documents.append({
                    "title": content["title"],
                    "content": markdown,
                    "source": "notion",
                    "date": content.get("created_time", "")[:10],
                })

        # Slack 수집
        if selection.slack_token and selection.slack_channel_ids:
            connector = SlackConnector(token=selection.slack_token)
            for i, channel_id in enumerate(selection.slack_channel_ids):
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Slack 채널 수집 중... ({i+1}/{len(selection.slack_channel_ids)})', 'percent': 15})}\n\n"
                messages = connector.get_messages(channel_id)
                markdown = slack_messages_to_markdown(messages, channel_name=channel_id)
                documents.append({
                    "title": f"Slack - {channel_id}",
                    "content": markdown,
                    "source": "slack",
                    "date": "",
                })

        # Google 수집
        if selection.google_credentials and selection.google_doc_ids:
            connector = GoogleConnector(credentials=selection.google_credentials)
            for i, doc_id in enumerate(selection.google_doc_ids):
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Google Docs 수집 중... ({i+1}/{len(selection.google_doc_ids)})', 'percent': 25})}\n\n"
                doc = connector.get_doc(doc_id)
                markdown = google_doc_to_markdown(doc)
                documents.append({
                    "title": doc.get("title", "Untitled"),
                    "content": markdown,
                    "source": "google",
                    "date": "",
                })

        if not documents:
            yield f"data: {json.dumps({'type': 'error', 'message': '수집된 문서가 없습니다'})}\n\n"
            return

        # 1단계: 전체 분석
        yield f"data: {json.dumps({'type': 'progress', 'message': 'Claude가 전체 문서를 분석 중...', 'percent': 35})}\n\n"
        analyzer = KnowledgeAnalyzer(api_key=api_key)
        schema = analyzer.analyze(documents, selection.folder_structure)

        # 2단계: 파일별 분류 + 변환
        classifier = NoteClassifier(api_key=api_key)
        all_titles = [d["title"] for d in documents]

        for i, doc in enumerate(documents):
            percent = 40 + int((i / len(documents)) * 55)
            yield f"data: {json.dumps({'type': 'progress', 'message': f'{doc[\"title\"]} 변환 중...', 'percent': percent})}\n\n"

            classified = classifier.classify(doc, schema, all_titles, selection.folder_structure)
            file_content = classifier.to_markdown(classified)
            file_path = f"{classified['folder']}/{doc['title']}.md"

            yield f"data: {json.dumps({'type': 'file', 'path': file_path, 'content': file_content})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'message': '마이그레이션 완료!', 'percent': 100, 'total': len(documents)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 2: 서버 실행 확인**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000/api/health` 접속
Expected: `{"status": "ok"}`

- [ ] **Step 3: 커밋**

```bash
git add backend/main.py
git commit -m "feat: add FastAPI main app with SSE migration endpoint"
```

---

## Task 9: 프론트엔드 프로젝트 셋업 + 공통 타입

**Files:**
- Create: `frontend/` (Next.js 프로젝트)
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/filesystem.ts`

- [ ] **Step 1: Next.js 프로젝트 생성**

```bash
cd ..  # obsidian-migration 루트로
npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir --import-alias "@/*"
```
프롬프트가 나오면 기본값으로 진행.

- [ ] **Step 2: 환경변수 파일 생성**

`frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 3: 공통 타입 작성**

`frontend/lib/types.ts`:
```typescript
export interface NotionPage {
  id: string
  title: string
}

export interface SlackChannel {
  id: string
  name: string
}

export interface GoogleDoc {
  id: string
  name: string
}

export interface SourceSelection {
  notion_token?: string
  notion_page_ids: string[]
  slack_token?: string
  slack_channel_ids: string[]
  google_credentials?: Record<string, string>
  google_doc_ids: string[]
  folder_structure: string[]
}

export type MigrationEvent =
  | { type: 'progress'; message: string; percent: number }
  | { type: 'file'; path: string; content: string }
  | { type: 'done'; message: string; percent: number; total: number }
  | { type: 'error'; message: string }
```

- [ ] **Step 4: API 클라이언트 작성**

`frontend/lib/api.ts`:
```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function fetchNotionPages(token: string) {
  const res = await fetch(`${BASE_URL}/api/sources/notion/pages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!res.ok) throw new Error('Notion 페이지 목록 조회 실패')
  return res.json()
}

export async function fetchSlackChannels(token: string) {
  const res = await fetch(`${BASE_URL}/api/sources/slack/channels`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!res.ok) throw new Error('Slack 채널 목록 조회 실패')
  return res.json()
}

export async function fetchGoogleDocs(credentials: Record<string, string>) {
  const res = await fetch(`${BASE_URL}/api/sources/google/docs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credentials }),
  })
  if (!res.ok) throw new Error('Google Docs 목록 조회 실패')
  return res.json()
}

export function streamMigration(selection: object): EventSource {
  // POST body를 query param으로 전달하기 위해 sessionStorage 활용
  sessionStorage.setItem('migration_selection', JSON.stringify(selection))
  return new EventSource(`${BASE_URL}/api/migrate`)
}
```

- [ ] **Step 5: File System API 래퍼 작성**

`frontend/lib/filesystem.ts`:
```typescript
export async function selectVaultFolder(): Promise<FileSystemDirectoryHandle> {
  if (!('showDirectoryPicker' in window)) {
    throw new Error('이 브라우저는 File System Access API를 지원하지 않습니다. Chrome 또는 Edge를 사용해주세요.')
  }
  return await (window as any).showDirectoryPicker({ mode: 'readwrite' })
}

export async function writeMarkdownFile(
  dirHandle: FileSystemDirectoryHandle,
  filePath: string,
  content: string
): Promise<void> {
  const parts = filePath.split('/')
  const filename = parts.pop()!

  let currentDir = dirHandle
  for (const part of parts) {
    currentDir = await currentDir.getDirectoryHandle(part, { create: true })
  }

  const fileHandle = await currentDir.getFileHandle(filename, { create: true })
  const writable = await fileHandle.createWritable()
  await writable.write(content)
  await writable.close()
}
```

- [ ] **Step 6: 커밋**

```bash
cd frontend
git add .
git commit -m "feat: initialize Next.js frontend with types, API client, filesystem utils"
```

---

## Task 10: OAuth 연결 페이지

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: 레이아웃 작성**

`frontend/app/layout.tsx`:
```tsx
import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Obsidian Migration',
  description: '당신의 지식을 Obsidian으로',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-white text-gray-900">
        <main className="max-w-2xl mx-auto px-4 py-12">
          {children}
        </main>
      </body>
    </html>
  )
}
```

- [ ] **Step 2: OAuth 연결 페이지 작성**

`frontend/app/page.tsx`:
```tsx
'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { fetchNotionPages, fetchSlackChannels } from '@/lib/api'

export default function ConnectPage() {
  const router = useRouter()
  const [notionToken, setNotionToken] = useState('')
  const [slackToken, setSlackToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleConnect() {
    if (!notionToken && !slackToken) {
      setError('최소 하나의 툴을 연결해주세요.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const tokens: Record<string, string> = {}
      if (notionToken) tokens.notion_token = notionToken
      if (slackToken) tokens.slack_token = slackToken
      sessionStorage.setItem('tokens', JSON.stringify(tokens))
      router.push('/select')
    } catch (e) {
      setError('연결 실패. 토큰을 확인해주세요.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Obsidian Migration</h1>
        <p className="text-gray-500 mt-1">툴을 연결하고 Obsidian vault로 지식을 이전하세요</p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Notion Integration Token</label>
          <input
            type="password"
            value={notionToken}
            onChange={e => setNotionToken(e.target.value)}
            placeholder="secret_..."
            className="w-full border rounded-lg px-3 py-2 text-sm"
          />
          <p className="text-xs text-gray-400 mt-1">notion.so/my-integrations 에서 발급</p>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Slack Bot Token</label>
          <input
            type="password"
            value={slackToken}
            onChange={e => setSlackToken(e.target.value)}
            placeholder="xoxb-..."
            className="w-full border rounded-lg px-3 py-2 text-sm"
          />
          <p className="text-xs text-gray-400 mt-1">api.slack.com/apps 에서 발급</p>
        </div>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <button
        onClick={handleConnect}
        disabled={loading}
        className="w-full bg-black text-white rounded-lg py-3 font-medium disabled:opacity-50"
      >
        {loading ? '연결 중...' : '연결하고 소스 선택 →'}
      </button>
    </div>
  )
}
```

- [ ] **Step 3: 개발 서버 실행 후 UI 확인**

```bash
cd frontend
npm run dev
```
브라우저에서 `http://localhost:3000` 확인.

- [ ] **Step 4: 커밋**

```bash
git add app/layout.tsx app/page.tsx
git commit -m "feat: add OAuth token input page"
```

---

## Task 11: 소스 선택 페이지

**Files:**
- Create: `frontend/app/select/page.tsx`
- Create: `frontend/components/SourceSelector.tsx`

- [ ] **Step 1: SourceSelector 컴포넌트 작성**

`frontend/components/SourceSelector.tsx`:
```tsx
interface Item {
  id: string
  name: string
}

interface Props {
  title: string
  items: Item[]
  selected: string[]
  onChange: (ids: string[]) => void
}

export function SourceSelector({ title, items, selected, onChange }: Props) {
  function toggle(id: string) {
    onChange(
      selected.includes(id) ? selected.filter(s => s !== id) : [...selected, id]
    )
  }

  function toggleAll() {
    onChange(selected.length === items.length ? [] : items.map(i => i.id))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-medium">{title}</h3>
        <button onClick={toggleAll} className="text-xs text-blue-600">
          {selected.length === items.length ? '전체 해제' : '전체 선택'}
        </button>
      </div>
      <div className="space-y-1 max-h-48 overflow-y-auto border rounded-lg p-2">
        {items.length === 0 && (
          <p className="text-sm text-gray-400 py-2 text-center">항목 없음</p>
        )}
        {items.map(item => (
          <label key={item.id} className="flex items-center gap-2 px-2 py-1 hover:bg-gray-50 rounded cursor-pointer">
            <input
              type="checkbox"
              checked={selected.includes(item.id)}
              onChange={() => toggle(item.id)}
              className="rounded"
            />
            <span className="text-sm">{item.name}</span>
          </label>
        ))}
      </div>
      <p className="text-xs text-gray-400 mt-1">{selected.length}개 선택됨</p>
    </div>
  )
}
```

- [ ] **Step 2: 소스 선택 페이지 작성**

`frontend/app/select/page.tsx`:
```tsx
'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { fetchNotionPages, fetchSlackChannels } from '@/lib/api'
import { SourceSelector } from '@/components/SourceSelector'
import type { NotionPage, SlackChannel } from '@/lib/types'

export default function SelectPage() {
  const router = useRouter()
  const [notionPages, setNotionPages] = useState<NotionPage[]>([])
  const [slackChannels, setSlackChannels] = useState<SlackChannel[]>([])
  const [selectedNotion, setSelectedNotion] = useState<string[]>([])
  const [selectedSlack, setSelectedSlack] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const tokens = JSON.parse(sessionStorage.getItem('tokens') ?? '{}')
    if (!tokens.notion_token && !tokens.slack_token) {
      router.replace('/')
      return
    }

    async function load() {
      try {
        if (tokens.notion_token) {
          const pages = await fetchNotionPages(tokens.notion_token)
          setNotionPages(pages)
        }
        if (tokens.slack_token) {
          const channels = await fetchSlackChannels(tokens.slack_token)
          setSlackChannels(channels)
        }
      } catch {
        setError('데이터 불러오기 실패. 토큰을 확인해주세요.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [router])

  function handleNext() {
    const selection = {
      selectedNotion,
      selectedSlack,
    }
    sessionStorage.setItem('selection', JSON.stringify(selection))
    router.push('/structure')
  }

  if (loading) return <p className="text-gray-500">불러오는 중...</p>

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">마이그레이션 소스 선택</h1>
        <p className="text-gray-500 mt-1">Obsidian으로 옮길 항목을 선택하세요</p>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="space-y-6">
        {notionPages.length > 0 && (
          <SourceSelector
            title="Notion 페이지"
            items={notionPages}
            selected={selectedNotion}
            onChange={setSelectedNotion}
          />
        )}
        {slackChannels.length > 0 && (
          <SourceSelector
            title="Slack 채널"
            items={slackChannels.map(c => ({ id: c.id, name: `#${c.name}` }))}
            selected={selectedSlack}
            onChange={setSelectedSlack}
          />
        )}
      </div>

      <button
        onClick={handleNext}
        disabled={selectedNotion.length === 0 && selectedSlack.length === 0}
        className="w-full bg-black text-white rounded-lg py-3 font-medium disabled:opacity-50"
      >
        다음: 폴더 구조 설정 →
      </button>
    </div>
  )
}
```

- [ ] **Step 3: 커밋**

```bash
git add app/select/ components/SourceSelector.tsx
git commit -m "feat: add source selector page"
```

---

## Task 12: 폴더 구조 편집 페이지

**Files:**
- Create: `frontend/app/structure/page.tsx`
- Create: `frontend/components/FolderEditor.tsx`

- [ ] **Step 1: FolderEditor 컴포넌트 작성**

`frontend/components/FolderEditor.tsx`:
```tsx
'use client'
import { useState } from 'react'

interface Props {
  folders: string[]
  onChange: (folders: string[]) => void
}

export function FolderEditor({ folders, onChange }: Props) {
  const [newFolder, setNewFolder] = useState('')

  function add() {
    const trimmed = newFolder.trim()
    if (!trimmed || folders.includes(trimmed)) return
    onChange([...folders, trimmed])
    setNewFolder('')
  }

  function remove(folder: string) {
    onChange(folders.filter(f => f !== folder))
  }

  function rename(index: number, value: string) {
    const updated = [...folders]
    updated[index] = value
    onChange(updated)
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {folders.map((folder, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="text-gray-400">📁</span>
            <input
              value={folder}
              onChange={e => rename(i, e.target.value)}
              className="flex-1 border rounded px-2 py-1 text-sm"
            />
            <button
              onClick={() => remove(folder)}
              className="text-red-400 hover:text-red-600 text-sm px-2"
            >
              삭제
            </button>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={newFolder}
          onChange={e => setNewFolder(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
          placeholder="새 폴더 이름"
          className="flex-1 border rounded px-2 py-1 text-sm"
        />
        <button
          onClick={add}
          className="border rounded px-3 py-1 text-sm hover:bg-gray-50"
        >
          추가
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 폴더 구조 편집 페이지 작성**

`frontend/app/structure/page.tsx`:
```tsx
'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { FolderEditor } from '@/components/FolderEditor'

const DEFAULT_FOLDERS = ['Projects', 'Areas', 'Resources', 'Inbox']

export default function StructurePage() {
  const router = useRouter()
  const [folders, setFolders] = useState<string[]>(DEFAULT_FOLDERS)

  function handleNext() {
    sessionStorage.setItem('folder_structure', JSON.stringify(folders))
    router.push('/migrate')
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">폴더 구조 설정</h1>
        <p className="text-gray-500 mt-1">
          Obsidian vault의 폴더 구조입니다. Claude가 각 노트를 알맞은 폴더에 분류합니다.
        </p>
      </div>

      <div className="bg-gray-50 rounded-lg p-4">
        <p className="text-sm text-gray-500 mb-3">
          기본값은 PARA 방법론입니다. 자유롭게 수정하세요.
        </p>
        <FolderEditor folders={folders} onChange={setFolders} />
      </div>

      <div className="text-sm text-gray-400 space-y-1">
        <p><strong>Projects</strong> — 현재 진행 중인 작업</p>
        <p><strong>Areas</strong> — 지속 관리 영역 (팀, 건강, 재무 등)</p>
        <p><strong>Resources</strong> — 주제별 참고자료</p>
        <p><strong>Inbox</strong> — 분류 전 임시 보관</p>
      </div>

      <button
        onClick={handleNext}
        disabled={folders.length === 0}
        className="w-full bg-black text-white rounded-lg py-3 font-medium disabled:opacity-50"
      >
        마이그레이션 시작 →
      </button>
    </div>
  )
}
```

- [ ] **Step 3: 커밋**

```bash
git add app/structure/ components/FolderEditor.tsx
git commit -m "feat: add folder structure editor page"
```

---

## Task 13: 마이그레이션 실행 페이지 + File System API

**Files:**
- Create: `frontend/app/migrate/page.tsx`
- Create: `frontend/components/MigrationProgress.tsx`

- [ ] **Step 1: MigrationProgress 컴포넌트 작성**

`frontend/components/MigrationProgress.tsx`:
```tsx
interface Props {
  percent: number
  message: string
  filesWritten: number
}

export function MigrationProgress({ percent, message, filesWritten }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex justify-between text-sm">
        <span className="text-gray-600">{message}</span>
        <span className="font-medium">{percent}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div
          className="bg-black h-2 rounded-full transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
      {filesWritten > 0 && (
        <p className="text-xs text-gray-400">{filesWritten}개 파일 저장됨</p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 마이그레이션 실행 페이지 작성**

`frontend/app/migrate/page.tsx`:
```tsx
'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { selectVaultFolder, writeMarkdownFile } from '@/lib/filesystem'
import { MigrationProgress } from '@/components/MigrationProgress'
import type { MigrationEvent, SourceSelection } from '@/lib/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type Status = 'idle' | 'selecting' | 'running' | 'done' | 'error'

export default function MigratePage() {
  const router = useRouter()
  const [status, setStatus] = useState<Status>('idle')
  const [percent, setPercent] = useState(0)
  const [message, setMessage] = useState('')
  const [filesWritten, setFilesWritten] = useState(0)
  const [error, setError] = useState('')

  async function handleStart() {
    setStatus('selecting')
    let dirHandle: FileSystemDirectoryHandle
    try {
      dirHandle = await selectVaultFolder()
    } catch {
      setStatus('idle')
      return
    }

    const tokens = JSON.parse(sessionStorage.getItem('tokens') ?? '{}')
    const selection = JSON.parse(sessionStorage.getItem('selection') ?? '{}')
    const folderStructure = JSON.parse(sessionStorage.getItem('folder_structure') ?? '["Projects","Areas","Resources","Inbox"]')

    const body: SourceSelection = {
      notion_token: tokens.notion_token,
      notion_page_ids: selection.selectedNotion ?? [],
      slack_token: tokens.slack_token,
      slack_channel_ids: selection.selectedSlack ?? [],
      google_doc_ids: [],
      folder_structure: folderStructure,
    }

    setStatus('running')
    setPercent(0)
    setFilesWritten(0)

    try {
      const res = await fetch(`${API_URL}/api/migrate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.body) throw new Error('스트림 없음')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const event: MigrationEvent = JSON.parse(line.slice(6))

          if (event.type === 'progress') {
            setPercent(event.percent)
            setMessage(event.message)
          } else if (event.type === 'file') {
            await writeMarkdownFile(dirHandle, event.path, event.content)
            setFilesWritten(n => n + 1)
          } else if (event.type === 'done') {
            setPercent(100)
            setMessage(event.message)
            setStatus('done')
          } else if (event.type === 'error') {
            throw new Error(event.message)
          }
        }
      }
    } catch (e: any) {
      setError(e.message ?? '마이그레이션 실패')
      setStatus('error')
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">마이그레이션</h1>
        <p className="text-gray-500 mt-1">Obsidian vault 폴더를 선택하면 시작됩니다</p>
      </div>

      {status === 'idle' && (
        <button
          onClick={handleStart}
          className="w-full bg-black text-white rounded-lg py-3 font-medium"
        >
          vault 폴더 선택 후 시작
        </button>
      )}

      {status === 'selecting' && (
        <p className="text-gray-500 text-center">폴더를 선택해주세요...</p>
      )}

      {(status === 'running' || status === 'done') && (
        <MigrationProgress percent={percent} message={message} filesWritten={filesWritten} />
      )}

      {status === 'done' && (
        <div className="space-y-3">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800">
            완료! Obsidian에서 vault를 열어 확인하세요.
          </div>
          <button
            onClick={() => router.push('/')}
            className="w-full border rounded-lg py-3 text-sm"
          >
            처음으로
          </button>
        </div>
      )}

      {status === 'error' && (
        <div className="space-y-3">
          <p className="text-red-500 text-sm">{error}</p>
          <button
            onClick={() => setStatus('idle')}
            className="w-full border rounded-lg py-3 text-sm"
          >
            다시 시도
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 전체 플로우 통합 테스트**

백엔드와 프론트엔드를 동시에 실행:
```bash
# 터미널 1
cd backend && uvicorn main:app --reload --port 8000

# 터미널 2
cd frontend && npm run dev
```

Chrome에서 `http://localhost:3000` 접속 후 전체 플로우 확인:
1. 토큰 입력 → 연결
2. 소스 선택
3. 폴더 구조 확인/편집
4. vault 폴더 선택 → 마이그레이션 실행
5. Obsidian에서 생성된 파일 확인

- [ ] **Step 4: 최종 커밋**

```bash
cd frontend
git add app/migrate/ components/MigrationProgress.tsx
git commit -m "feat: add migration execution page with File System Access API and SSE streaming"
```

---

## 전체 테스트 실행

```bash
cd backend
pytest tests/ -v
```
Expected: 전체 테스트 PASSED
