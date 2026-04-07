import json
import anthropic


class KnowledgeAnalyzer:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def analyze(self, documents: list[dict], folder_structure: list[str]) -> dict:
        doc_summaries = "\n\n".join(
            f"[{d['source']}] 제목: {d['title']}\n내용: {d['content'][:800]}"
            for d in documents
        )

        response = await self.client.messages.create(
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

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()
        return json.loads(text)
