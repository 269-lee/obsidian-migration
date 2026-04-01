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
