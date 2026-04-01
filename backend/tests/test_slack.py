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
