"""
주제 중심 자율 마이그레이션 러너 v2
- 소스(채널/페이지) 단위가 아닌 주제 단위로 노트 생성
- 여러 채널/페이지의 같은 주제 내용을 하나의 지식 노트로 합성
- 에러 발생 시 자동 재시도
- 결과물을 migration_output_v2/ 폴더에 저장
"""

import asyncio
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

# ── 설정 ──────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
NOTION_TOKEN      = os.getenv("NOTION_CLIENT_SECRET")
SLACK_TOKEN       = os.getenv("SLACK_CLIENT_SECRET", "").lstrip(".")
VAULT_PATH        = os.getenv("OBSIDIAN_VAULT_PATH", "")

FOLDER_STRUCTURE = ["Projects", "Areas", "Resources", "Archive"]

OUTPUT_DIR        = Path(__file__).parent / "migration_output_v2"
LOG_FILE          = Path(__file__).parent / "migration_log_v2.txt"
CACHE_FILE        = Path(__file__).parent / "migration_cache.json"
VAULT_CACHE_FILE  = Path(__file__).parent / "vault_schema_cache.json"

MAX_RETRIES = 3
RETRY_DELAY = 5

# ── 로거 ──────────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ── Vault 분석 (캐시 지원) ────────────────────────────────────────────────────

async def get_vault_schema() -> dict | None:
    if not VAULT_PATH or not Path(VAULT_PATH).exists():
        log("OBSIDIAN_VAULT_PATH 없음 — 기본 폴더 구조 사용", "WARN")
        return None

    if VAULT_CACHE_FILE.exists():
        log(f"Vault 스키마 캐시 로드 ({VAULT_CACHE_FILE.name})")
        with open(VAULT_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)

    from ai.vault_analyzer import VaultAnalyzer
    log(f"Vault 분석 중: {VAULT_PATH}")
    analyzer = VaultAnalyzer(api_key=ANTHROPIC_API_KEY)
    schema = await analyzer.analyze(VAULT_PATH)
    log(f"Vault 분석 완료 — 폴더: {schema.get('folders', [])}, 노트 수: {schema.get('total_notes', 0)}")

    with open(VAULT_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    log(f"Vault 스키마 캐시 저장")

    # Vault 폴더 구조로 FOLDER_STRUCTURE 업데이트
    vault_folders = [f["path"] for f in schema.get("folder_structure", [])]
    if vault_folders:
        global FOLDER_STRUCTURE
        FOLDER_STRUCTURE = vault_folders
        log(f"폴더 구조를 Vault 기준으로 변경: {FOLDER_STRUCTURE}")

    return schema

# ── 수집 (캐시 지원) ──────────────────────────────────────────────────────────

NOTION_CACHE_FILE     = Path(__file__).parent / "cache_notion.json"
SLACK_CACHE_FILE      = Path(__file__).parent / "cache_slack.json"
CHUNKS_CACHE_FILE     = Path(__file__).parent / "cache_chunks.json"
CLUSTERS_CACHE_FILE   = Path(__file__).parent / "cache_clusters.json"
SYNTHESIS_CACHE_FILE  = Path(__file__).parent / "cache_synthesis.json"

def load_cache(path: Path) -> list[dict] | None:
    if path.exists():
        log(f"캐시 발견 ({path.name}) — API 재수집 생략")
        with open(path, encoding="utf-8") as f:
            docs = json.load(f)
        log(f"캐시에서 {len(docs)}개 문서 로드")
        return docs
    return None

def save_cache(documents: list[dict], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    log(f"수집 결과 캐시 저장 ({path.name})")

def collect_notion_documents() -> list[dict]:
    """Notion 문서만 수집"""
    from connectors.notion import NotionConnector
    from converter.markdown import notion_blocks_to_markdown

    documents = []
    if not (NOTION_TOKEN and not NOTION_TOKEN.startswith("...")):
        return documents

    log("Notion 페이지 수집 중...")
    try:
        notion = NotionConnector(token=NOTION_TOKEN)
        pages = notion.list_pages()
        log(f"Notion {len(pages)}개 페이지 발견")
        for i, page in enumerate(pages):
            try:
                content = notion.get_page_content(page["id"])
                markdown = notion_blocks_to_markdown(content["blocks"])
                if len(markdown.strip()) < 150:
                    continue
                if content["title"].strip().lower() in ("untitled", "제목 없음", ""):
                    continue
                documents.append({
                    "title": content["title"],
                    "content": markdown,
                    "source": "notion",
                    "date": content.get("created_time", "")[:10],
                    "project_hint": content.get("project_hint"),
                })
                log(f"  Notion [{i+1}/{len(pages)}] {content['title']}")
            except Exception as e:
                log(f"  Notion {page['id']} 실패: {e}", "WARN")
    except Exception as e:
        log(f"Notion 연결 실패: {e}", "ERROR")

    return documents


def collect_slack_documents() -> list[dict]:
    """Slack 스레드 단위로 수집"""
    from connectors.slack import SlackConnector

    documents = []
    if not (SLACK_TOKEN and SLACK_TOKEN.startswith("xoxb-")):
        return documents

    log("Slack 채널 수집 중 (스레드 단위)...")
    try:
        slack = SlackConnector(token=SLACK_TOKEN)
        channels = slack.list_channels()
        log(f"Slack {len(channels)}개 채널 발견")
        for i, ch in enumerate(channels):
            try:
                threads = slack.get_threads(ch["id"], ch["name"])
                if not threads:
                    continue
                documents.extend(threads)
                log(f"  Slack [{i+1}/{len(channels)}] #{ch['name']} → {len(threads)}개 스레드")
            except Exception as e:
                log(f"  Slack #{ch['name']} 실패: {e}", "WARN")
    except Exception as e:
        log(f"Slack 연결 실패: {e}", "ERROR")

    return documents

# ── AI 파이프라인 ─────────────────────────────────────────────────────────────

async def chunk_all(documents: list[dict], clusterer, cache_file: Path = None) -> list[dict]:
    """모든 문서를 병렬로 chunk 분해 (문서 단위 증분 캐시 지원)"""
    # 기존 캐시에서 이미 처리된 문서 로드
    all_chunks: list[dict] = []
    processed_titles: set[str] = set()

    if cache_file and cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            all_chunks = json.load(f)
        processed_titles = {c["source_title"] for c in all_chunks}
        log(f"chunk 캐시 로드 ({cache_file.name}) — {len(processed_titles)}개 문서 / {len(all_chunks)}개 chunk")

    # 아직 처리 안 된 문서만 필터링
    remaining = [d for d in documents if d["title"] not in processed_titles]
    if not remaining:
        log(f"모든 문서 chunk 완료 (캐시). 총 {len(all_chunks)}개 chunk")
        return all_chunks

    log(f"미처리 문서 {len(remaining)}개 chunk 분해 중... (전체 {len(documents)}개 중)")

    cache_lock = asyncio.Lock()

    async def chunk_one(doc, idx):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                chunks = await clusterer.chunk_document(doc)
                log(f"  chunk [{idx+1}/{len(remaining)}] {doc['title']} -> {len(chunks)}개 주제")
                return chunks
            except Exception as e:
                log(f"  chunk 실패 ({attempt}/{MAX_RETRIES}) {doc['title']}: {e}", "WARN")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)
        return []

    async def chunk_one_and_save(doc, idx):
        chunks = await chunk_one(doc, idx)
        if cache_file and chunks:
            async with cache_lock:
                all_chunks.extend(chunks)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        elif chunks:
            all_chunks.extend(chunks)
        return chunks

    # 병렬 실행 (동시 5개씩)
    batch_size = 5
    for i in range(0, len(remaining), batch_size):
        batch = remaining[i:i + batch_size]
        await asyncio.gather(*[chunk_one_and_save(doc, i + j) for j, doc in enumerate(batch)])

    log(f"총 {len(all_chunks)}개 chunk 추출 완료")
    return all_chunks


async def run_ai_pipeline(documents: list[dict], vault_schema: dict = None) -> list[dict]:
    from ai.topic_clusterer import TopicClusterer
    from ai.synthesizer import NoteSynthesizer
    from ai.hierarchy_analyzer import HierarchyAnalyzer

    clusterer = TopicClusterer(api_key=ANTHROPIC_API_KEY)
    synthesizer = NoteSynthesizer(api_key=ANTHROPIC_API_KEY)
    hierarchy_analyzer = HierarchyAnalyzer(api_key=ANTHROPIC_API_KEY)

    # 1. 문서 → chunk 분해 (캐시 활용)
    all_chunks = await chunk_all(documents, clusterer, cache_file=CHUNKS_CACHE_FILE)
    if not all_chunks:
        log("추출된 chunk가 없습니다.", "ERROR")
        return []

    # 2. chunk → 주제 클러스터링 (캐시 지원)
    if CLUSTERS_CACHE_FILE.exists():
        log(f"클러스터 캐시 로드 ({CLUSTERS_CACHE_FILE.name})")
        with open(CLUSTERS_CACHE_FILE, encoding="utf-8") as f:
            clusters = json.load(f)
        log(f"캐시에서 {len(clusters)}개 클러스터 로드")
    else:
        log("주제별 군집화 중...")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                clusters = await clusterer.cluster_chunks(all_chunks, FOLDER_STRUCTURE, vault_schema=vault_schema)
                log(f"클러스터 {len(clusters)}개 생성")
                for cl in clusters:
                    log(f"  [{cl['folder']}] {cl['name']} ({len(cl['chunks'])}개 chunk)")
                with open(CLUSTERS_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(clusters, f, ensure_ascii=False, indent=2)
                log(f"클러스터 캐시 저장 ({CLUSTERS_CACHE_FILE.name})")
                break
            except Exception as e:
                log(f"클러스터링 실패 ({attempt}/{MAX_RETRIES}): {e}", "WARN")
                if attempt == MAX_RETRIES:
                    raise
                await asyncio.sleep(RETRY_DELAY * attempt)

    # 3. 계층 분석 (프로젝트 노트 vs 하위 노트 구분)
    log("계층 구조 분석 중...")
    hierarchy_map: dict[str, dict] = {}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            hierarchy = await hierarchy_analyzer.analyze(clusters)
            hierarchy_map = {h["cluster_name"]: h for h in hierarchy}
            project_count = sum(1 for h in hierarchy if h["is_project"])
            child_count = sum(1 for h in hierarchy if not h["is_project"] and h.get("parent"))
            log(f"  프로젝트 노트: {project_count}개 / 하위 노트: {child_count}개 / 독립: {len(hierarchy) - project_count - child_count}개")
            for h in hierarchy:
                if h["is_project"]:
                    log(f"  [PROJECT] {h['cluster_name']}")
                elif h.get("parent"):
                    log(f"    └ [CHILD→{h['parent']}] {h['cluster_name']}")
            break
        except Exception as e:
            log(f"계층 분석 실패 ({attempt}/{MAX_RETRIES}): {e}", "WARN")
            if attempt == MAX_RETRIES:
                log("계층 분석 포기 — 모든 노트를 독립 노트로 처리", "WARN")
                hierarchy_map = {cl["name"]: {"cluster_name": cl["name"], "is_project": False, "parent": None} for cl in clusters}
            else:
                await asyncio.sleep(RETRY_DELAY * attempt)

    # 4. 클러스터 → 통합 노트 합성
    def cluster_content_length(cluster: dict) -> int:
        """클러스터의 총 내용 길이 (summary + key_points 합산)"""
        total = 0
        for c in cluster["chunks"]:
            total += len(c.get("summary", ""))
            total += sum(len(kp) for kp in c.get("key_points", []))
        return total

    MIN_CONTENT_LENGTH = 300  # 이 미만이면 합성 스킵
    rich_clusters = [cl for cl in clusters if cluster_content_length(cl) >= MIN_CONTENT_LENGTH and cl["name"].lower() != "general"]
    thin_clusters  = [cl for cl in clusters if cluster_content_length(cl) < MIN_CONTENT_LENGTH or cl["name"].lower() == "general"]
    log(f"클러스터 {len(clusters)}개 중 합성 대상 {len(rich_clusters)}개, 스킵(내용 부족) {len(thin_clusters)}개")

    all_cluster_names = [cl["name"] for cl in clusters]
    child_title_map: dict[str, list[str]] = {}  # parent_cluster_name → [child_note_titles]

    # 합성 캐시 로드
    synthesis_cache: dict[str, dict] = {}
    if SYNTHESIS_CACHE_FILE.exists():
        with open(SYNTHESIS_CACHE_FILE, encoding="utf-8") as f:
            synthesis_cache = json.load(f)
        log(f"합성 캐시 로드 — {len(synthesis_cache)}개 노트")

    def save_synthesis_cache():
        with open(SYNTHESIS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(synthesis_cache, f, ensure_ascii=False, indent=2)

    synthesized: list[dict] = []

    # 내용 부족 클러스터는 Archive로 바로 저장
    for cluster in thin_clusters:
        raw = "\n\n".join(f"### {c['topic_hint']}\n{c['summary']}" for c in cluster["chunks"])
        synthesized.append({
            "cluster_name": cluster["name"],
            "note_title": cluster["name"],
            "note": {"title": cluster["name"], "frontmatter": {}, "content": raw},
            "cluster": cluster,
            "is_project": False,
            "parent": None,
            "fallback": True,
        })

    # 이미 합성된 클러스터는 캐시에서 로드
    cached_clusters = [cl for cl in rich_clusters if cl["name"] in synthesis_cache]
    pending_clusters = [cl for cl in rich_clusters if cl["name"] not in synthesis_cache]
    for cluster in cached_clusters:
        entry = synthesis_cache[cluster["name"]]
        synthesized.append(entry)
        if entry.get("parent"):
            child_title_map.setdefault(entry["parent"], []).append(entry["note_title"])

    log(f"합성 대상 {len(rich_clusters)}개 중 캐시 {len(cached_clusters)}개, 신규 {len(pending_clusters)}개")

    # 병렬 합성 (동시 3개)
    if pending_clusters:
        log(f"{len(pending_clusters)}개 노트 병렬 합성 중 (동시 3개)...")
    semaphore = asyncio.Semaphore(3)
    cache_lock = asyncio.Lock()

    async def synthesize_one(cluster, idx):
        h_info = hierarchy_map.get(cluster["name"], {"is_project": False, "parent": None})
        is_project = h_info.get("is_project", False)
        parent = h_info.get("parent")
        label = "[PROJECT]" if is_project else (f"[→{parent}]" if parent else "")
        log(f"  합성 [{idx+1}/{len(pending_clusters)}] {cluster['name']} {label}")

        async with semaphore:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    note = await synthesizer.synthesize(
                        cluster, all_cluster_names,
                        vault_schema=vault_schema,
                        is_project=is_project,
                        parent_project=parent,
                    )
                    entry = {
                        "cluster_name": cluster["name"],
                        "note_title": note["title"],
                        "note": note,
                        "cluster": cluster,
                        "is_project": is_project,
                        "parent": parent,
                    }
                    async with cache_lock:
                        synthesis_cache[cluster["name"]] = entry
                        save_synthesis_cache()
                    if parent:
                        child_title_map.setdefault(parent, []).append(note["title"])
                    return entry
                except Exception as e:
                    log(f"    합성 실패 ({attempt}/{MAX_RETRIES}): {e}", "WARN")
                    if attempt == MAX_RETRIES:
                        log(f"    {cluster['name']} 포기 — 원본 chunk 저장", "ERROR")
                        raw = "\n\n".join(f"### {c['topic_hint']}\n{c['summary']}" for c in cluster["chunks"])
                        entry = {
                            "cluster_name": cluster["name"],
                            "note_title": cluster["name"],
                            "note": {"title": cluster["name"], "frontmatter": {}, "content": raw},
                            "cluster": cluster,
                            "is_project": False,
                            "parent": None,
                            "fallback": True,
                        }
                        async with cache_lock:
                            synthesis_cache[cluster["name"]] = entry
                            save_synthesis_cache()
                        return entry
                    await asyncio.sleep(RETRY_DELAY * attempt)

    results_parallel = await asyncio.gather(*[synthesize_one(cl, i) for i, cl in enumerate(pending_clusters)])
    synthesized.extend(results_parallel)

    # 5. 마크다운 변환 및 경로 결정
    results = []
    for s in synthesized:
        if s.get("fallback"):
            results.append({
                "path": f"Archive/{s['note_title'].replace('/', '-')}.md",
                "content": f"---\ntitle: {s['note_title']}\n---\n\n{s['note']['content']}",
            })
            continue

        child_notes = child_title_map.get(s["cluster_name"], []) if s["is_project"] else []
        content = synthesizer.to_markdown(
            s["note"], s["cluster"],
            is_project=s["is_project"],
            child_notes=child_notes,
            parent_project=s["parent"],
        )
        safe_title = s["note_title"].replace("/", "-").replace("\\", "-")
        results.append({
            "path": f"{s['cluster']['folder']}/{safe_title}.md",
            "content": content,
        })

    return results

# ── 저장 ──────────────────────────────────────────────────────────────────────

def save_results(results: list[dict]):
    OUTPUT_DIR.mkdir(exist_ok=True)
    for r in results:
        file_path = OUTPUT_DIR / r["path"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(r["content"], encoding="utf-8")
        log(f"  저장: {r['path']}")

# ── 메인 ─────────────────────────────────────────────────────────────────────

async def run_slack_phase(notion_results: list[dict], vault_schema: dict = None):
    """Phase 2: Slack 스레드 수집 → 매핑 → A/C/archive 처리"""
    from ai.topic_clusterer import TopicClusterer
    from ai.synthesizer import NoteSynthesizer
    from ai.slack_mapper import SlackMapper

    clusterer   = TopicClusterer(api_key=ANTHROPIC_API_KEY)
    synthesizer = NoteSynthesizer(api_key=ANTHROPIC_API_KEY)
    mapper      = SlackMapper(api_key=ANTHROPIC_API_KEY)

    # Slack 수집
    slack_docs = load_cache(SLACK_CACHE_FILE)
    if slack_docs is None:
        slack_docs = collect_slack_documents()
        if slack_docs:
            save_cache(slack_docs, SLACK_CACHE_FILE)

    if not slack_docs:
        log("Slack 문서 없음 — Phase 2 스킵")
        return []

    log(f"Slack {len(slack_docs)}개 스레드 문서 수집 완료")

    # Slack chunk + cluster
    slack_chunks = await chunk_all(slack_docs, clusterer)
    if not slack_chunks:
        return []

    log("Slack 주제 군집화 중...")
    slack_clusters = await clusterer.cluster_chunks(slack_chunks, FOLDER_STRUCTURE, vault_schema=vault_schema)
    log(f"Slack 클러스터 {len(slack_clusters)}개 생성")

    # Notion 노트 인덱스 (매핑용 요약 생성)
    notion_index = []
    for r in notion_results:
        # path에서 제목 추출 (folder/title.md → title)
        title = Path(r["path"]).stem
        # frontmatter에서 summary 추출 (없으면 앞 200자)
        content_preview = r["content"].split("---", 2)[-1].strip()[:200]
        notion_index.append({"title": title, "summary": content_preview, "folder": str(Path(r["path"]).parent)})

    # Slack 클러스터 → Notion 노트 매핑
    log("Slack ↔ Notion 노트 매핑 중...")
    mapping = await mapper.map(slack_clusters, notion_index)
    mapping_by_name = {m["cluster_name"]: m for m in mapping}

    results = []
    # notion_results를 title → content 딕셔너리로 변환 (A방안 수정용)
    notion_content_map = {Path(r["path"]).stem: r for r in notion_results}
    all_note_titles = [Path(r["path"]).stem for r in notion_results]

    for cluster in slack_clusters:
        m = mapping_by_name.get(cluster["name"], {"treatment": "archive", "target_note": None})
        treatment = m["treatment"]
        target = m.get("target_note")
        log(f"  [{treatment.upper()}] {cluster['name']}" + (f" → {target}" if target else ""))

        if treatment == "A" and target and target in notion_content_map:
            # 기존 노트에 Slack 논의 섹션 추가
            existing = notion_content_map[target]
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    enriched = await synthesizer.enrich_with_slack(existing["content"], cluster)
                    existing["content"] = enriched  # in-place 업데이트
                    break
                except Exception as e:
                    if attempt == MAX_RETRIES:
                        log(f"    enrich 실패 — archive로 처리: {e}", "WARN")
                        treatment = "archive"
                    else:
                        await asyncio.sleep(RETRY_DELAY * attempt)

        elif treatment == "C" and target:
            # 연결된 하위 노트 생성
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    note = await synthesizer.synthesize_slack_child(cluster, target, all_note_titles)
                    content = synthesizer.to_markdown(note, cluster, parent_project=target)
                    safe_title = note["title"].replace("/", "-").replace("\\", "-")
                    # 부모 노트와 같은 폴더에 저장
                    parent_folder = notion_content_map.get(target, {}).get("path", "Archive/")
                    folder = str(Path(parent_folder).parent)
                    results.append({"path": f"{folder}/{safe_title}.md", "content": content})
                    # 부모 노트 관련 노트 섹션에도 추가
                    if target in notion_content_map:
                        notion_content_map[target]["content"] += f"\n- [[{note['title']}]]"
                    break
                except Exception as e:
                    if attempt == MAX_RETRIES:
                        log(f"    child 생성 실패 — archive로 처리: {e}", "WARN")
                        treatment = "archive"
                    else:
                        await asyncio.sleep(RETRY_DELAY * attempt)

        if treatment == "archive":
            chunks_raw = "\n\n".join(f"### {c['topic_hint']}\n{c['summary']}" for c in cluster["chunks"])
            safe_name = cluster["name"].replace("/", "-")
            results.append({
                "path": f"Archive/Slack/{safe_name}.md",
                "content": f"---\ntitle: {cluster['name']}\nsource: slack\n---\n\n{chunks_raw}",
            })

    return results


async def main():
    log("=" * 60)
    log("Obsidian 마이그레이션 v2 시작 (Notion 우선, Slack 매핑)")
    log(f"폴더 구조: {' / '.join(FOLDER_STRUCTURE)}")
    log("=" * 60)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            vault_schema = await get_vault_schema()

            # ── Phase 1: Notion 기반 계층 구축 ──────────────────────────────
            log("\n[Phase 1] Notion 계층 구축")
            notion_docs = load_cache(NOTION_CACHE_FILE)
            if notion_docs is None:
                notion_docs = collect_notion_documents()
                if notion_docs:
                    save_cache(notion_docs, NOTION_CACHE_FILE)

            if not notion_docs:
                log("Notion 문서가 없습니다.", "ERROR")
                sys.exit(1)
            log(f"Notion {len(notion_docs)}개 문서 수집 완료")

            notion_results = await run_ai_pipeline(notion_docs, vault_schema=vault_schema)

            # ── Phase 2: Slack 매핑 ──────────────────────────────────────────
            log("\n[Phase 2] Slack 매핑")
            slack_results = await run_slack_phase(notion_results, vault_schema=vault_schema)

            # notion_results는 Phase 2에서 in-place 수정될 수 있으므로 합쳐서 저장
            all_results = notion_results + slack_results
            save_results(all_results)

            log("=" * 60)
            log(f"완료! Notion {len(notion_results)}개 + Slack {len(slack_results)}개 → migration_output_v2/")
            log("=" * 60)
            return

        except Exception as e:
            log(f"실패 (시도 {attempt}/{MAX_RETRIES}): {e}", "ERROR")
            log(traceback.format_exc(), "ERROR")
            if attempt < MAX_RETRIES:
                log(f"{RETRY_DELAY * attempt}초 후 재시도...")
                await asyncio.sleep(RETRY_DELAY * attempt)
            else:
                log("최대 재시도 초과.", "ERROR")
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
