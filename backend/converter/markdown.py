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
