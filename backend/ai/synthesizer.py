"""
클러스터 합성기
- 하나의 topic cluster에 속한 chunk들을 Obsidian 지식 노트로 합성
- 원문 복사가 아닌 핵심 의사결정/진행현황/액션아이템 추출
"""
import json
import anthropic


class NoteSynthesizer:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def synthesize(
        self,
        cluster: dict,
        all_cluster_names: list[str],
        vault_schema: dict = None,
        is_project: bool = False,
        child_notes: list[str] = None,
        parent_project: str = None,
    ) -> dict:
        """cluster → 통합 Obsidian 노트

        Args:
            is_project: True면 프로젝트 노트 (최상위), False면 일반/하위 노트
            child_notes: 이 프로젝트에 속한 하위 노트 제목 목록 (is_project=True일 때)
            parent_project: 이 노트가 속한 상위 프로젝트 이름 (is_project=False일 때)
        """
        child_notes = child_notes or []

        chunks_text = "\n\n".join(
            f"[{c['source_type'].upper()} | {c['source_title']}]\n"
            f"핵심: {c['summary']}\n"
            f"포인트: {chr(10).join('- ' + p for p in c.get('key_points', []))}"
            for c in cluster["chunks"]
        )

        sources = list({c["source_title"] for c in cluster["chunks"]})
        all_notes = [n for n in all_cluster_names if n != cluster["name"]]

        vault_context = ""
        example_fm = {}
        if vault_schema:
            vault_context = f"""
사용자의 Obsidian vault 스타일:
- 노트 구조 패턴: {vault_schema.get('note_style', {}).get('content_pattern', '')}
- 헤딩 구조: {vault_schema.get('note_style', {}).get('heading_structure', '')}
- 태그 방식: {vault_schema.get('frontmatter_schema', {}).get('tag_pattern', '')}
- 날짜 형식: {vault_schema.get('frontmatter_schema', {}).get('date_format', '')}
- 네이밍 규칙: {vault_schema.get('naming_convention', '')}

위 스타일에 맞게 노트를 작성하세요.
"""
            example_fm = vault_schema.get("example_frontmatter", {})

        # 노트 유형별 추가 지시사항
        if is_project:
            type_instruction = """이 노트는 **프로젝트 노트(최상위)**입니다.
- 프로젝트의 목표, 배경, 전체 진행 흐름, 주요 결정사항을 중심으로 작성
- 세부 미팅/이슈는 요약만 언급하고 하위 노트 링크로 대체"""
        elif parent_project:
            type_instruction = f"""이 노트는 **[[{parent_project}]] 프로젝트의 하위 노트**입니다.
- 해당 미팅/이슈/작업의 구체적인 내용에 집중
- 본문 첫 줄에 '> [[{parent_project}]] 하위 노트' 형식으로 상위 프로젝트를 명시"""
        else:
            type_instruction = "이 노트는 **독립 노트**입니다. 주제에 집중하여 작성하세요."

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            messages=[{
                "role": "user",
                "content": f"""다음은 "{cluster['name']}" 주제와 관련된 여러 소스의 내용입니다:

{chunks_text}

{type_instruction}

이 내용들을 하나의 Obsidian 지식 노트로 합성해주세요.
{vault_context}
요구사항:
- 구체적인 내용, 날짜, 수치, 담당자, 결정 배경을 최대한 보존
- 나중에 검색했을 때 찾을 수 있도록 키워드를 풍부하게 포함
- 현재 상태/진행상황 명확히 기술
- 시간 흐름이 있으면 날짜순으로 정리
- 주요 결정사항, 미해결 이슈, 액션아이템 명확히 구분
- 내부 팀원만 언급 (외부 협업사 직원 제외)
- 관련 노트: {', '.join(all_notes[:20])} → 연관된 것은 [[노트이름]]으로 링크
- 노트 길이를 아끼지 말 것 — 디테일할수록 좋음

frontmatter 예시 (사용자 스타일):
{json.dumps(example_fm, ensure_ascii=False) if example_fm else '없음'}

반드시 아래 구분자 형식으로만 응답하세요 (JSON 아님):

===TITLE===
노트 제목 (구체적이고 검색 가능하게)

===FRONTMATTER===
{{"tags": ["관련 태그"], "people": ["내부 팀원 이름만"], "sources": {json.dumps(sources, ensure_ascii=False)}, "status": "active|ongoing|resolved|archived", "date": "YYYY-MM-DD"}}

===CONTENT===
상세하고 풍부한 마크다운 내용 (헤딩, 날짜, 결정 배경, 수치 등 포함)"""
            }]
        )

        text_resp = response.content[0].text.strip()

        # 구분자 파싱
        def extract_section(text: str, marker: str) -> str:
            markers = ["===TITLE===", "===FRONTMATTER===", "===CONTENT==="]
            start = text.find(marker)
            if start == -1:
                return ""
            start += len(marker)
            # 다음 구분자 위치 찾기
            end = len(text)
            for m in markers:
                if m != marker:
                    pos = text.find(m, start)
                    if pos != -1 and pos < end:
                        end = pos
            return text[start:end].strip()

        title = extract_section(text_resp, "===TITLE===")
        fm_raw = extract_section(text_resp, "===FRONTMATTER===")
        content = extract_section(text_resp, "===CONTENT===")

        if not title or not content:
            raise ValueError(f"응답 파싱 실패: TITLE={bool(title)}, CONTENT={bool(content)}")

        try:
            frontmatter = json.loads(fm_raw) if fm_raw else {}
        except json.JSONDecodeError:
            frontmatter = {"sources": sources}

        return {"title": title, "frontmatter": frontmatter, "content": content}

    def to_markdown(
        self,
        note: dict,
        cluster: dict,
        is_project: bool = False,
        child_notes: list[str] = None,
        parent_project: str = None,
    ) -> str:
        child_notes = child_notes or []
        fm = note["frontmatter"]
        lines = ["---"]
        lines.append(f"title: {note['title']}")

        # 프로젝트 노트: type 필드 추가
        if is_project:
            lines.append("type: project")
        # 하위 노트: project 필드 추가
        elif parent_project:
            lines.append(f"project: \"[[{parent_project}]]\"")

        for key, value in fm.items():
            if key == "title":
                continue
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
        lines.append(note["content"])

        # 프로젝트 노트: 하위 노트 목록 섹션 추가
        if is_project and child_notes:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## 관련 노트")
            for child in child_notes:
                lines.append(f"- [[{child}]]")

        return "\n".join(lines)

    async def enrich_with_slack(self, existing_markdown: str, slack_cluster: dict) -> str:
        """Treatment A: 기존 Notion 노트에 Slack 논의 섹션 추가"""
        chunks_text = "\n\n".join(
            f"[{c['source_date']}] {c['summary']}"
            for c in slack_cluster["chunks"]
        )

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""다음 Slack 대화 내용을 Obsidian 노트에 추가할 "## Slack 논의" 섹션으로 요약해주세요.

Slack 내용:
{chunks_text}

요구사항:
- 핵심 결정사항, 액션아이템, 의견 위주로 간결하게
- 날짜 정보가 있으면 포함
- 마크다운 형식 (소제목, 불릿 허용)
- "## Slack 논의" 헤더는 포함하지 말 것 (호출부에서 추가함)

요약 내용만 출력하세요 (JSON 아님):"""
            }]
        )

        slack_section = response.content[0].text.strip()
        return f"{existing_markdown}\n\n---\n\n## Slack 논의\n\n{slack_section}"

    async def synthesize_slack_child(
        self,
        slack_cluster: dict,
        parent_note_title: str,
        all_note_titles: list[str],
    ) -> dict:
        """Treatment C: Slack 내용을 부모 노트에 연결된 하위 노트로 생성"""
        chunks_text = "\n\n".join(
            f"[{c.get('source_date', '')}] {c['summary']}\n"
            + "\n".join(f"- {p}" for p in c.get("key_points", []))
            for c in slack_cluster["chunks"]
        )

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""다음은 [[{parent_note_title}]]와 관련된 Slack 대화입니다:

{chunks_text}

이 내용을 [[{parent_note_title}]]의 하위 Obsidian 노트로 작성해주세요.

요구사항:
- 본문 첫 줄: "> [[{parent_note_title}]] 관련 Slack 논의"
- 핵심 결정, 의견, 액션아이템 중심
- 관련 노트가 있으면 [[노트이름]]으로 링크 (후보: {', '.join(all_note_titles[:15])})

반드시 아래 JSON으로만 응답하세요:
{{
  "title": "노트 제목 (날짜나 주제 포함, 구체적으로)",
  "frontmatter": {{
    "tags": [],
    "date": "YYYY-MM-DD",
    "status": "archived"
  }},
  "content": "마크다운 본문"
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
