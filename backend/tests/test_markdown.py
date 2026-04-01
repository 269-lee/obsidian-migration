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
