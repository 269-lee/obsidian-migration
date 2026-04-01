# Obsidian Migration Solution — Design Spec
Date: 2026-04-01

## Overview

여러 툴(Notion, Slack, Google Workspace)에 분산된 사용자 데이터를 Obsidian vault로 마이그레이션하는 웹 서비스. 단순 변환이 아니라 노트 간 연결과 property 기반 지식 그래프를 자동으로 구성하는 것이 핵심 가치.

## 목표 (1차 MVP)

- Notion(페이지), Slack(채널), Google Workspace(Docs/Drive) 데이터 수집
- 사용자가 마이그레이션할 소스를 선택
- PARA 기반 폴더 구조 제안 + 사용자 커스텀
- Claude가 전체 데이터 분석 후 property 스키마 설계
- 각 노트에 wikilink + frontmatter property 자동 생성
- File System Access API로 Obsidian vault에 직접 저장

## 운영 방식

- 초기: 내부 도구
- 추후: 퍼블릭 SaaS 전환 가능성 열어둠 (설계에 반영)

---

## 아키텍처

```
[Frontend — Next.js / Vercel]
  OAuth 로그인 → 소스 선택 → 폴더 구조 편집 → 마이그레이션 실행 → vault 저장
  ↕ HTTP / SSE 스트리밍
[Backend — FastAPI / Railway]
  데이터 수집 → Claude 분석 → Markdown 변환 → 스트리밍 응답
```

**핵심 원칙:** 사용자 데이터는 백엔드를 거쳐가기만 하고 저장되지 않음. 변환된 파일은 SSE로 프론트에 스트리밍 → File System Access API로 vault에 직접 기록.

### Tech Stack

| 영역 | 기술 |
|------|------|
| Frontend | Next.js (App Router) |
| Backend | Python FastAPI |
| AI | Claude API (Anthropic) |
| Frontend 배포 | Vercel |
| Backend 배포 | Railway |

---

## 사용자 플로우

```
1. 접속 및 툴 연결
   └── Notion / Slack / Google OAuth 로그인

2. 소스 선택
   ├── Notion: 페이지 목록 체크박스
   ├── Slack: 채널 목록 체크박스
   └── Google: Docs/Drive 파일 목록 체크박스

3. 폴더 구조 설정
   ├── 기본 PARA 구조 제안
   │   ├── Projects/
   │   ├── Areas/
   │   ├── Resources/
   │   └── Inbox/
   └── 사용자가 폴더명 수정 / 추가 / 삭제

4. 마이그레이션 실행 (2단계)
   ├── [1단계] 전체 데이터 수집 + Claude 분석
   │   ├── 핵심 개념, 사람, 프로젝트 추출
   │   ├── 노트 간 연관 관계 매핑
   │   └── property 스키마 설계
   ├── [2단계] 파일별 생성
   │   ├── Markdown 변환
   │   ├── frontmatter property 생성
   │   ├── 본문 내 [[wikilink]] 삽입
   │   └── 폴더 분류
   └── 진행률 실시간 표시 (SSE)

5. Vault 저장
   ├── "폴더 선택" → File System Access API
   └── .md 파일들 vault에 직접 기록
```

---

## 지식 그래프 설계

Obsidian의 핵심 가치인 노트 간 연결을 자동으로 구성하는 것이 이 서비스의 핵심 차별점.

### 2단계 AI 처리

**1단계 — 전체 분석 (파일 생성 전)**

모든 수집 데이터를 Claude가 통합 분석:
- 반복 등장하는 핵심 개념/태그 추출
- 언급된 사람, 프로젝트, 도구 식별
- 노트 간 잠재적 연결 관계 매핑
- 전체에 적용할 공통 property 스키마 확정

**2단계 — 파일별 생성**

1단계 스키마 기반으로 각 파일 생성:
- frontmatter property 채움
- 본문 내 연관 개념에 `[[wikilink]]` 삽입

### Property 스키마 (예시)

```yaml
---
title: "..."
source: notion | slack | google
date: 2024-01-01
tags: [project-x, design, ux]
people: [[홍길동]], [[김철수]]
project: [[Project X]]
related: [[노트A]], [[노트B]]
status: active | archived
---
```

스키마는 사용자 데이터 분석 결과에 따라 Claude가 동적으로 설계.

---

## 컴포넌트 구조

### Frontend (Next.js)

```
app/
├── page.tsx                 # 툴 연결 (OAuth)
├── select/page.tsx          # 소스 선택 (체크박스)
├── structure/page.tsx       # 폴더 구조 편집
└── migrate/page.tsx         # 실행 + 진행률 + vault 저장
```

### Backend (FastAPI)

```
api/
├── connectors/
│   ├── notion.py            # Notion API 수집
│   ├── slack.py             # Slack API 수집
│   └── google.py            # Google API 수집
├── ai/
│   ├── analyzer.py          # 1단계: 전체 분석 + 스키마 설계
│   └── classifier.py        # 2단계: 파일별 property + wikilink 생성
├── converter/
│   └── markdown.py          # HTML/JSON → Markdown 변환
└── main.py                  # SSE 스트리밍 엔드포인트
```

### 데이터 흐름

```
소스 수집 → 전체 분석(Claude) → 스키마 확정
→ 파일별 변환 + property 생성(Claude) → SSE 스트리밍
→ 프론트엔드 File System API → vault 저장
```

---

## 2차 MVP (범위 외)

- 지속 동기화 (변경사항 자동 반영)
- 과금 / 사용자 인증
- 추가 소스 연동 (GitHub, Linear 등)
