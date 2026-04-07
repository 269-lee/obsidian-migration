import json
import anthropic


class NoteClassifier:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def classify(
        self,
        document: dict,
        schema: dict,
        all_titles: list[str],
        folder_structure: list[str],
    ) -> dict:
        response = await self.client.messages.create(
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
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()
        return json.loads(text)

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
