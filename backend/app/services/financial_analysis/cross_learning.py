"""유사 공고 크로스 러닝 — 같은 카테고리 금융 공고의 분석 데이터를 상담에 참조

상담 중인 공고에 금리/한도 등이 없을 때,
같은 카테고리의 다른 공고에서 유사 데이터를 가져와 비교 참고자료로 제공한다.
"""

import json


def get_similar_financial_announcements(
    announcement_id: int,
    category: str,
    title: str,
    db_conn,
    limit: int = 3,
) -> list[dict]:
    """같은 카테고리의 금융 분석 완료된 유사 공고 조회

    Returns:
        list of {"title": ..., "financial_summary": {...}}
    """
    if not db_conn:
        return []

    try:
        cur = db_conn.cursor()

        # 같은 카테고리 또는 제목에 유사 키워드가 있는 금융 공고
        # financial_details가 있는 공고만 (분석 완료)
        cur.execute("""
            SELECT a.announcement_id, a.title, a.support_amount, a.deadline_date,
                   da.deep_analysis
            FROM announcements a
            JOIN announcement_analysis da ON a.announcement_id = da.announcement_id
            WHERE a.announcement_id != %s
              AND da.deep_analysis IS NOT NULL
              AND da.deep_analysis::text LIKE '%%financial_details%%'
              AND (
                  a.category = %s
                  OR a.title ILIKE '%%정책자금%%'
                  OR a.title ILIKE '%%융자%%'
                  OR a.title ILIKE '%%보증%%'
              )
            ORDER BY
                CASE WHEN a.category = %s THEN 0 ELSE 1 END,
                a.created_at DESC
            LIMIT %s
        """, (announcement_id, category, category, limit))

        rows = cur.fetchall()
        results = []

        for row in rows:
            deep = row.get("deep_analysis") or {}
            if isinstance(deep, str):
                deep = json.loads(deep)

            fd = deep.get("financial_details")
            if not fd:
                continue

            # 핵심 정보만 추출
            loan = fd.get("loan_conditions") or {}
            coll = fd.get("collateral_guarantee") or {}
            elig = fd.get("eligibility_financial") or {}

            summary = {}
            if loan.get("interest_rate_range"):
                summary["금리"] = loan["interest_rate_range"]
            if loan.get("loan_limit_max") or loan.get("loan_limit_sme"):
                summary["한도"] = loan.get("loan_limit_max") or loan.get("loan_limit_sme")
            if loan.get("repayment_period_facility"):
                summary["시설자금 상환"] = loan["repayment_period_facility"]
            if loan.get("repayment_period_operating"):
                summary["운전자금 상환"] = loan["repayment_period_operating"]
            if coll.get("guarantee_agencies"):
                summary["보증기관"] = coll["guarantee_agencies"]
            if elig.get("credit_restriction"):
                summary["신용등급"] = elig["credit_restriction"]

            if summary:
                results.append({
                    "title": row["title"],
                    "support_amount": row.get("support_amount"),
                    "financial_summary": summary,
                })

        return results

    except Exception as e:
        print(f"[CrossLearning] Error: {e}")
        return []


def build_cross_reference_context(similar_announcements: list[dict]) -> str:
    """유사 공고 데이터를 상담 프롬프트용 텍스트로 변환"""
    if not similar_announcements:
        return ""

    lines = [
        "\n[유사 정책자금/융자 공고 참고 데이터] ★ 현재 공고에 정보가 없을 때 아래 유사 공고를 비교 참고하세요"
    ]

    for i, ann in enumerate(similar_announcements, 1):
        title = ann["title"][:50]
        lines.append(f"\n  ▶ 유사공고 {i}: {title}")
        for key, val in ann["financial_summary"].items():
            lines.append(f"    - {key}: {val}")

    lines.append("\n  ※ 위 데이터는 유사 공고 참고용이며, 현재 공고와 조건이 다를 수 있습니다.")

    return "\n".join(lines)
