"""
API 비용 예측 및 경고 테스트
- 각 단계별 예상 토큰 수 계산
- CLAUDE.md 원칙: 예상 비용을 사용자에게 먼저 알려야 함
"""

import pytest


# 모델별 가격 (per 1M tokens, USD)
PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},   # chunk 분해용
    "claude-sonnet-4-6":         {"input": 3.00, "output": 15.00},  # 클러스터링, 합성용
}

# 단계별 예상 토큰 (문서 1개 기준 평균치)
TOKEN_ESTIMATES = {
    "chunking": {
        "model": "claude-haiku-4-5-20251001",
        "input_tokens_per_doc": 2000,   # 문서 평균 2000 토큰
        "output_tokens_per_doc": 500,   # chunk 목록 출력 500 토큰
    },
    "clustering": {
        "model": "claude-sonnet-4-6",
        "input_tokens_per_batch": 8000,  # 배치당 chunk 묶음
        "output_tokens_per_batch": 1000,
        "batch_size": 20,                # 배치당 chunk 수
    },
    "synthesis": {
        "model": "claude-sonnet-4-6",
        "input_tokens_per_cluster": 5000,  # 클러스터당 입력
        "output_tokens_per_cluster": 2000, # 합성 노트 출력
    },
}

COST_WARNING_THRESHOLD_USD = 10.0  # $10 이상이면 사용자 확인 필요 (CLAUDE.md 규칙)


def estimate_cost(doc_count: int, cluster_count: int) -> dict:
    """전체 파이프라인 예상 비용 계산"""
    costs = {}

    # Phase 1: Chunking (haiku)
    chunk_est = TOKEN_ESTIMATES["chunking"]
    chunk_price = PRICING[chunk_est["model"]]
    chunk_cost = (
        doc_count * chunk_est["input_tokens_per_doc"] / 1_000_000 * chunk_price["input"]
        + doc_count * chunk_est["output_tokens_per_doc"] / 1_000_000 * chunk_price["output"]
    )
    costs["chunking"] = chunk_cost

    # Phase 2: Clustering (sonnet)
    cluster_est = TOKEN_ESTIMATES["clustering"]
    cluster_price = PRICING[cluster_est["model"]]
    batch_count = max(1, doc_count // cluster_est["batch_size"])
    cluster_cost = (
        batch_count * cluster_est["input_tokens_per_batch"] / 1_000_000 * cluster_price["input"]
        + batch_count * cluster_est["output_tokens_per_batch"] / 1_000_000 * cluster_price["output"]
    )
    costs["clustering"] = cluster_cost

    # Phase 3: Synthesis (sonnet)
    synth_est = TOKEN_ESTIMATES["synthesis"]
    synth_price = PRICING[synth_est["model"]]
    synth_cost = (
        cluster_count * synth_est["input_tokens_per_cluster"] / 1_000_000 * synth_price["input"]
        + cluster_count * synth_est["output_tokens_per_cluster"] / 1_000_000 * synth_price["output"]
    )
    costs["synthesis"] = synth_cost

    costs["total"] = sum(costs.values())
    return costs


class TestCostEstimation:
    def test_small_migration_under_threshold(self):
        """소규모 마이그레이션(문서 10개)은 $10 미만이어야 함"""
        costs = estimate_cost(doc_count=10, cluster_count=5)
        assert costs["total"] < COST_WARNING_THRESHOLD_USD, (
            f"소규모 마이그레이션 예상 비용 ${costs['total']:.2f}가 임계값을 초과합니다"
        )

    def test_medium_migration_cost_estimate(self):
        """중규모 마이그레이션(문서 100개)의 예상 비용 계산"""
        costs = estimate_cost(doc_count=100, cluster_count=30)
        assert costs["total"] > 0, "비용이 0이면 계산 오류"
        assert "chunking" in costs
        assert "clustering" in costs
        assert "synthesis" in costs

    def test_large_migration_exceeds_threshold(self):
        """대규모 마이그레이션(문서 500개)은 $10 이상 → 사용자 확인 필요"""
        costs = estimate_cost(doc_count=500, cluster_count=100)
        # 이 테스트는 경고 조건이 실제로 트리거되는지 확인
        # 실패하면 가격 책정이 잘못된 것
        assert costs["total"] >= COST_WARNING_THRESHOLD_USD, (
            f"500개 문서 마이그레이션 비용이 ${costs['total']:.2f}로 너무 저렴합니다. "
            "토큰 추정치를 확인하세요."
        )

    def test_retry_multiplies_cost(self):
        """재시도 3회 시 비용이 3배가 됨을 검증"""
        base_costs = estimate_cost(doc_count=50, cluster_count=20)
        retry_costs = estimate_cost(doc_count=50 * 3, cluster_count=20 * 3)
        # 재시도로 인한 비용 증가 비율 확인
        ratio = retry_costs["total"] / base_costs["total"]
        assert 2.5 <= ratio <= 3.5, f"재시도 비용 비율이 예상(3x)과 다릅니다: {ratio:.1f}x"

    def test_cost_breakdown_by_phase(self):
        """단계별 비용 분류가 정확한지 검증"""
        costs = estimate_cost(doc_count=50, cluster_count=20)
        assert costs["chunking"] > 0
        assert costs["clustering"] > 0
        assert costs["synthesis"] > 0
        assert abs(costs["total"] - (costs["chunking"] + costs["clustering"] + costs["synthesis"])) < 0.001

    def test_sonnet_more_expensive_than_haiku(self):
        """sonnet이 haiku보다 비싸야 함 (가격 설정 검증)"""
        haiku = PRICING["claude-haiku-4-5-20251001"]
        sonnet = PRICING["claude-sonnet-4-6"]
        assert sonnet["input"] > haiku["input"], "sonnet 입력 가격이 haiku보다 저렴합니다"
        assert sonnet["output"] > haiku["output"], "sonnet 출력 가격이 haiku보다 저렴합니다"


class TestCostWarningThreshold:
    def test_threshold_is_10_dollars(self):
        """CLAUDE.md 규칙: $10 이상 시 사용자 확인 필요"""
        assert COST_WARNING_THRESHOLD_USD == 10.0

    def test_should_warn_user(self):
        """비용 경고 함수 동작 검증"""
        def should_warn(cost: float) -> bool:
            return cost >= COST_WARNING_THRESHOLD_USD

        assert should_warn(10.0) is True
        assert should_warn(9.99) is False
        assert should_warn(50.0) is True
