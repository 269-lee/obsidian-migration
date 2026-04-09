"""
캐시 자동 정리 스크립트
- 오래된 cache_*.json 파일 삭제
- 오래된 migration_output_v2 아카이브 정리
- GitHub Actions cleanup.yml에서 주간 실행됨
"""

import json
import os
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).parent.parent
CACHE_FILES = [
    BACKEND_DIR / "cache_chunks.json",
    BACKEND_DIR / "cache_clusters.json",
    BACKEND_DIR / "cache_notion.json",
    BACKEND_DIR / "cache_slack.json",
    BACKEND_DIR / "cache_synthesis.json",
    BACKEND_DIR / "vault_schema_cache.json",
    BACKEND_DIR / "migration_cache.json",
]

OUTPUT_DIR = BACKEND_DIR / "migration_output_v2"
CACHE_MAX_AGE_DAYS = 7       # 캐시 파일 최대 보관 기간
ARCHIVE_MAX_AGE_DAYS = 30    # 아카이브 최대 보관 기간


def get_file_age_days(path: Path) -> float:
    """파일의 수정 시간 기준 경과 일수"""
    mtime = path.stat().st_mtime
    now = datetime.now(timezone.utc).timestamp()
    return (now - mtime) / 86400


def validate_cache(path: Path) -> tuple[bool, str]:
    """캐시 파일 유효성 검사. (valid, reason) 반환"""
    if not path.exists():
        return False, "파일 없음"

    if path.stat().st_size == 0:
        return False, "파일이 비어있음"

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data is None:
            return False, "JSON이 null"
        return True, "정상"
    except json.JSONDecodeError as e:
        return False, f"JSON 파싱 오류: {e}"


def cleanup_old_caches(max_age_days: int = CACHE_MAX_AGE_DAYS, dry_run: bool = False) -> list[str]:
    """오래되거나 손상된 캐시 파일 삭제"""
    deleted = []

    for path in CACHE_FILES:
        if not path.exists():
            continue

        age = get_file_age_days(path)
        valid, reason = validate_cache(path)

        should_delete = age > max_age_days or not valid

        if should_delete:
            reason_str = f"{age:.0f}일 경과" if age > max_age_days else f"손상: {reason}"
            print(f"{'[DRY RUN] ' if dry_run else ''}삭제: {path.name} ({reason_str})")
            if not dry_run:
                path.unlink()
                deleted.append(str(path))
        else:
            print(f"유지: {path.name} ({age:.0f}일, {reason})")

    return deleted


def cleanup_old_archives(max_age_days: int = ARCHIVE_MAX_AGE_DAYS, dry_run: bool = False) -> list[str]:
    """오래된 migration_output_v2 아카이브 정리"""
    deleted = []

    if not OUTPUT_DIR.exists():
        print(f"출력 디렉토리 없음: {OUTPUT_DIR}")
        return deleted

    # Archive/ 하위 디렉토리만 정리 (Projects/, Areas/ 등은 건드리지 않음)
    archive_dir = OUTPUT_DIR / "Archive"
    if not archive_dir.exists():
        return deleted

    for item in archive_dir.iterdir():
        if not item.is_dir():
            continue
        age = get_file_age_days(item)
        if age > max_age_days:
            print(f"{'[DRY RUN] ' if dry_run else ''}아카이브 삭제: {item.name} ({age:.0f}일 경과)")
            if not dry_run:
                shutil.rmtree(item)
                deleted.append(str(item))

    return deleted


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN 모드 (실제 삭제 안 함) ===\n")

    print("=== 캐시 파일 정리 ===")
    deleted_caches = cleanup_old_caches(dry_run=dry_run)

    print("\n=== 아카이브 정리 ===")
    deleted_archives = cleanup_old_archives(dry_run=dry_run)

    total = len(deleted_caches) + len(deleted_archives)
    print(f"\n완료: 캐시 {len(deleted_caches)}개, 아카이브 {len(deleted_archives)}개 {'삭제 예정' if dry_run else '삭제됨'} (총 {total}개)")


if __name__ == "__main__":
    main()
