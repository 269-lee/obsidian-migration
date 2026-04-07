"""
Obsidian Vault 스타일 분석기
- 전체 vault의 모든 .md 파일에서 경로 + frontmatter + 본문 첫 300자 추출
- Claude가 폴더 구조, 메타데이터 스키마, 노트 작성 스타일을 파악
"""
import json
import re
from pathlib import Path
import anthropic


def extract_file_map(vault_path: str) -> list[dict]:
    """Vault 전체 .md 파일에서 경로 + frontmatter + 본문 앞부분 추출"""
    vault = Path(vault_path)
    file_map = []

    for md_file in sorted(vault.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = str(md_file.relative_to(vault))

            # frontmatter 추출
            frontmatter = {}
            body_start = 0
            if text.startswith("---"):
                end = text.find("---", 3)
                if end != -1:
                    fm_text = text[3:end].strip()
                    body_start = end + 3
                    for line in fm_text.splitlines():
                        if ":" in line:
                            k, _, v = line.partition(":")
                            frontmatter[k.strip()] = v.strip()

            body_preview = text[body_start:body_start + 300].strip()

            file_map.append({
                "path": rel_path,
                "frontmatter": frontmatter,
                "preview": body_preview,
            })
        except Exception:
            continue

    return file_map


class VaultAnalyzer:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def analyze(self, vault_path: str) -> dict:
        """Vault 전체 구조 분석 → 스타일 스키마 반환"""
        file_map = extract_file_map(vault_path)

        # Claude에게 전달할 요약 (경로 + frontmatter + 미리보기)
        vault_summary = json.dumps(file_map, ensure_ascii=False)

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""다음은 사용자의 Obsidian vault에 있는 모든 노트의 경로, frontmatter, 본문 미리보기입니다:

{vault_summary}

이 데이터를 분석해서 이 사용자가 어떤 방식으로 지식을 정리하는지 파악해주세요.

반드시 아래 JSON으로만 응답하세요:
{{
  "folder_structure": [
    {{"path": "폴더경로", "purpose": "이 폴더의 용도 설명"}}
  ],
  "frontmatter_schema": {{
    "common_keys": ["자주 쓰는 frontmatter 키 목록"],
    "tag_pattern": "태그 방식 설명 (예: #area/work, status: active 등)",
    "date_format": "날짜 형식 (예: YYYY-MM-DD)"
  }},
  "note_style": {{
    "heading_structure": "헤딩 구조 패턴 설명",
    "content_pattern": "노트 작성 패턴 설명 (항목/서술/표 등)",
    "language": "주 작성 언어"
  }},
  "example_frontmatter": {{
    "예시 frontmatter 키1": "예시 값1",
    "예시 frontmatter 키2": "예시 값2"
  }},
  "naming_convention": "파일 네이밍 규칙 설명"
}}"""
            }]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()

        schema = json.loads(text)
        schema["total_notes"] = len(file_map)
        schema["folders"] = list({f["path"].split("/")[0] for f in file_map if "/" in f["path"]})
        return schema
