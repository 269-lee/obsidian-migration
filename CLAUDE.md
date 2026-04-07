# CLAUDE.md — obsidian-migration

노션, 슬랙을 Obsidian vault로 마이그레이션하는 도구입니다.

---

## 프로젝트 구조

```
obsidian-migration/
├── backend/        # FastAPI (Python) — 데이터 수집, 변환, AI 분류
├── frontend/       # Next.js (TypeScript) — 마이그레이션 UI
├── landing/        # 랜딩 페이지
├── docs/           # 문서
└── start.sh        # 로컬 실행 스크립트
```

---

## 기술 스택

**Backend** (`backend/`)
- Python, FastAPI
- 배포: Railway (`railway.toml`, `Procfile`)
- 연동 소스: Notion API, Slack API, Google Docs API
- AI: Claude API
  - `claude-haiku-4-5-20251001` — chunk 분해 (대량, 저비용)
  - `claude-sonnet-4-6` — 클러스터링, 합성, 매핑 (고품질)

**Frontend** (`frontend/`)
- TypeScript, Next.js
- 백엔드와 REST API로 통신 (`FRONTEND_URL` / `http://localhost:3000`)

---

## 마이그레이션 알고리즘

### 설계 원칙

- **Notion이 계층 구조의 기준**이다. Notion 문서가 프로젝트 노트와 하위 노트를 결정한다.
- **Slack은 Notion을 보강**한다. 독립적인 지식 구조를 만들지 않고, 기존 Notion 노트에 붙이거나 하위 노트로 연결된다.
- 모든 노트는 **프로젝트 노트(최상위)** 또는 **하위 노트(프로젝트에 연결)** 또는 **독립 노트** 중 하나다.

---

### Phase 1 — Notion 기반 계층 구축

```
Notion 수집
  → chunk_document()     문서를 주제 단위 chunk로 분해
  → cluster_chunks()     유사 chunk끼리 군집화 (소스 무관)
  → HierarchyAnalyzer    프로젝트 노트 vs 하위 노트 판별
  → NoteSynthesizer      클러스터 → Obsidian 노트 합성
  → 저장
```

**계층 판별 신호 (HierarchyAnalyzer):**
- Notion `project` property: 이 노트가 어느 프로젝트에 속하는지 명시적 신호
- chunk 수: 많을수록 비중 있는 주제일 가능성 높음
- 다른 클러스터에서의 언급 빈도: 자주 언급될수록 상위 프로젝트 가능성 높음
- AI 내용 판단: 전략/목표/서비스 전체 다루면 프로젝트, 특정 날짜/이슈 중심이면 하위 노트

**결과물 구조:**
```
# 프로젝트 노트 (frontmatter: type: project)
---
title: 맞추다 실기 확장
type: project
---
...본문...

## 관련 노트
- [[실기 기획 킥오프 2024-03-15]]
- [[실기 UI 이슈 #23]]

# 하위 노트 (frontmatter: project: "[[프로젝트명]]")
---
title: 실기 기획 킥오프 2024-03-15
project: "[[맞추다 실기 확장]]"
---
> [[맞추다 실기 확장]] 하위 노트
...
```

---

### Phase 2 — Slack 매핑

```
Slack 수집 (스레드 단위)
  → chunk_document()
  → cluster_chunks()
  → SlackMapper          각 클러스터를 Notion 노트와 비교
       ├── A (맥락 동일)  → 기존 Notion 노트에 "## Slack 논의" 섹션 추가
       ├── C (맥락 다름)  → 연결된 하위 노트 별도 생성 (project 링크 포함)
       └── archive        → Archive/Slack/[주제].md 로 저장
```

**Slack 수집 방식:**
- 스레드가 있는 메시지 → replies 포함해서 스레드 1개 = 문서 1개
- 스레드 없는 단발 메시지 → 날짜별로 묶어서 문서 1개

**SlackMapper 판단 기준:**
- A: Slack 논의가 Notion 노트와 완전히 같은 주제 → 내용 보강
- C: 관련은 있지만 다른 시점의 논의, 파생된 이슈 등 → 별도 하위 노트
- archive: 매칭되는 Notion 노트 없음, 또는 잡담/공지 등 지식 가치 낮음

---

## 파이프라인 구분

이 프로젝트에는 **두 개의 독립적인 파이프라인**이 존재한다.

### v1 — 웹 UI 기반 (`main.py` + frontend)
- FastAPI가 SSE로 프론트엔드에 진행상황 스트리밍
- 사용자가 UI에서 API 키, 페이지/채널 선택 후 실행
- `analyzer.py` + `classifier.py` 사용 (문서 단위 분류)
- 출력: `migration_output/`

### v2 — CLI 파이프라인 (`run_migration.py`)
- 서버 환경변수로 토큰 관리, 전체 자동 실행
- 주제 단위 클러스터링 → 계층 분석 → 합성 (더 정교한 알고리즘)
- 출력: `migration_output_v2/`
- **현재 주력으로 사용하는 파이프라인**

---

## 주요 모듈 (Backend)

| 모듈 | 역할 | 파이프라인 |
|------|------|-----------|
| `connectors/notion.py` | Notion 페이지 수집 (project property 포함) | 공통 |
| `connectors/slack.py` | Slack 스레드 단위 수집 | 공통 |
| `connectors/google.py` | Google Docs 수집 | v1 |
| `converter/markdown.py` | 각 소스 → Markdown 변환 | 공통 |
| `ai/analyzer.py` | 전체 문서 분석 → vault 스키마 생성 | v1 |
| `ai/classifier.py` | 문서 단위 분류 → Obsidian 노트 | v1 |
| `ai/topic_clusterer.py` | 문서 → chunk 분해, chunk → 주제 클러스터링 | v2 |
| `ai/hierarchy_analyzer.py` | 클러스터 계층 판별 (프로젝트 / 하위 / 독립) | v2 |
| `ai/synthesizer.py` | 클러스터 → Obsidian 노트 합성, Slack 보강 처리 | v2 |
| `ai/slack_mapper.py` | Slack 클러스터 ↔ Notion 노트 매핑 (A/C/archive 판단) | v2 |
| `ai/vault_analyzer.py` | 기존 Obsidian vault 구조 분석 → 스타일 반영 | v2 |
| `run_migration.py` | 전체 파이프라인 실행 (Phase 1 → Phase 2) | v2 |

---

## 캐시 구조 (v2 파이프라인)

재실행 시 API 호출 최소화를 위해 단계별로 캐시한다. 모두 `backend/` 디렉토리에 위치.

| 파일 | 단계 | 내용 | 삭제 시 |
|------|------|------|---------|
| `cache_notion.json` | 수집 | Notion 페이지 원문 | Notion 재수집 (API 비용 없음) |
| `cache_slack.json` | 수집 | Slack 스레드 원문 | Slack 재수집 (API 비용 없음) |
| `cache_chunks.json` | chunk 분해 | 문서별 chunk 목록 | **haiku로 전체 재chunk (과금)** |
| `cache_clusters.json` | 클러스터링 | 주제별 클러스터 | **sonnet으로 재클러스터링 (과금)** |
| `cache_synthesis.json` | 합성 | 노트별 합성 결과 | **sonnet으로 재합성 (과금)** |
| `vault_schema_cache.json` | vault 분석 | Obsidian vault 구조 | Vault 재분석 (과금) |

**특정 단계부터 재실행:** 해당 단계 캐시 파일만 삭제
- 합성만 다시: `cache_synthesis.json` 삭제
- 클러스터링부터 재시작: `cache_clusters.json` + `cache_synthesis.json` 삭제
- 전체 재실행: 모든 cache_*.json + vault_schema_cache.json 삭제

```bash
python run_migration.py
```

---

## 로컬 실행

```bash
./start.sh
# 또는 개별 실행
cd backend && uvicorn main:app --reload   # v1 웹 API
cd frontend && npm run dev                # 프론트엔드

# v2 CLI 파이프라인 직접 실행
cd backend && python run_migration.py
```

**환경 변수** (`backend/.env`):
- `ANTHROPIC_API_KEY` — Claude API 키
- `NOTION_CLIENT_SECRET` — Notion integration token
- `SLACK_CLIENT_SECRET` — Slack bot token (xoxb-로 시작)
- `OBSIDIAN_VAULT_PATH` — 기존 vault 경로 (선택, 스타일 분석용)

## 출력 구조

```
backend/
├── migration_output/      # v1 출력 (웹 UI 파이프라인)
└── migration_output_v2/   # v2 출력 (CLI 파이프라인)
    ├── Projects/          # 프로젝트 노트
    ├── Areas/             # 영역 노트
    ├── Resources/         # 리소스 노트
    └── Archive/           # 아카이브 (내용 부족 or Slack 미매칭)
        └── Slack/         # Slack archive 노트
```

---

## 핵심 원칙

- 코드 수정 전 반드시 관련 모듈 먼저 읽기
- 알고리즘 변경 시 이 CLAUDE.md의 마이그레이션 알고리즘 섹션도 함께 업데이트
- 외부 API(Notion, Slack) 연동 시 인증 방식 및 rate limit 먼저 확인
- 소통 언어: **한국어**

---

## 크레딧 낭비 방지 규칙

**Anthropic API 크레딧이 낭비될 가능성이 있는 상황에서는 실행을 멈추고 반드시 사용자에게 확인을 받아야 한다.**

낭비 가능성이 있는 상황 예시:
- 캐시 없이 대량 문서를 처음부터 재처리하려는 경우
- 이미 실패한 방식과 동일한 방식으로 재실행하려는 경우
- 예상 비용이 $10 이상인 작업을 자동으로 시작하려는 경우
- 파이프라인 중간 단계의 캐시가 없어 앞 단계부터 전부 재실행되는 경우

확인 방법: 실행 전 예상 비용과 이유를 설명하고, 사용자 승인 후 진행

---

## API 비용 관련 개발 원칙 (시행착오로 학습한 내용)

> 이 프로젝트에서 반복적인 크레딧 낭비가 발생했다. 다시는 같은 실수를 반복하지 않기 위해 아래 원칙을 반드시 지킨다.

### 1. 개발 시작 전 비용 설계 의무

API를 호출하는 기능을 개발하기 전에 반드시 아래 질문에 답해야 한다:

- **중간에 실패하면 어떻게 되는가?** 처음부터 다시 과금되는가?
- **각 단계의 결과가 캐시되는가?** 캐시 없으면 재실행 시 전액 재과금
- **실패율이 높은 구간은 어디인가?** 재시도 3회 = 비용 3배
- **총 API 호출 횟수 × 예상 토큰 수** 를 계산해서 예상 비용을 사용자에게 먼저 제시

### 2. 파이프라인 캐시 설계 원칙

**API를 호출하는 모든 단계는 반드시 증분 캐시를 가져야 한다.**

| 단계 | 캐시 방식 |
|------|---------|
| 수집 (Notion/Slack) | 전체 완료 후 저장 (OK — API 비용 없음) |
| Chunking | **문서 1개 완료마다 즉시 저장** |
| Clustering | 배치 1개 완료마다 즉시 저장 |
| Synthesis | **노트 1개 완료마다 즉시 저장** |

캐시 없이 "전체 완료 후 저장" 방식은 절대 사용하지 않는다.

### 3. 고유 식별자 원칙

캐시의 dedup key는 반드시 **고유한 값**을 써야 한다.
- ❌ `source_title` — "Untitled"처럼 중복될 수 있음 → 수백 개 문서가 하나로 처리됨
- ✅ `page_id` 또는 `title + date` 조합 사용

### 4. 실행 전 체크리스트

비용이 발생하는 작업을 실행하기 전에 반드시 확인:
- [ ] 모든 단계에 증분 캐시가 있는가?
- [ ] 캐시 key가 고유한가?
- [ ] 예상 비용을 계산해서 사용자에게 먼저 알렸는가?
- [ ] 실패 시 재시도 비용까지 포함했는가?
