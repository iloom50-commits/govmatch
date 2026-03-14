"""
매칭 품질 검증 스크립트
- 다양한 기업 프로필로 매칭을 실행하여 결과의 적합성을 검증
- 사용법: python test_matching_quality.py
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.core.matcher import get_matches_for_user

# 테스트 프로필 정의
TEST_PROFILES = [
    {
        "name": "서울 미용실 (소상공인)",
        "profile": {
            "business_number": "TEST000001",
            "company_name": "뷰티살롱",
            "address_city": "서울",
            "establishment_date": "2022-06-01",
            "industry_code": "96121",  # 두발 미용업
            "revenue_bracket": "1억 미만",
            "employee_count_bracket": "5인 미만",
            "interests": "소상공인,시설개선",
        },
        "expect_keywords": ["소상공인", "미용", "서울"],
        "reject_keywords": ["수출", "반도체", "R&D"],
    },
    {
        "name": "경기 IT 스타트업 (3년차)",
        "profile": {
            "business_number": "TEST000002",
            "company_name": "테크스타트업",
            "address_city": "경기",
            "establishment_date": "2023-03-15",
            "industry_code": "62010",  # 소프트웨어 개발
            "revenue_bracket": "1억~5억",
            "employee_count_bracket": "5인~10인",
            "interests": "기술개발,창업지원,디지털전환",
        },
        "expect_keywords": ["창업", "기술", "R&D", "스타트업", "IT", "디지털"],
        "reject_keywords": ["소상공인", "자영업", "전통시장"],
    },
    {
        "name": "부산 음식점 (소상공인)",
        "profile": {
            "business_number": "TEST000003",
            "company_name": "부산곰탕",
            "address_city": "부산",
            "establishment_date": "2020-01-10",
            "industry_code": "56111",  # 한식 일반 음식점업
            "revenue_bracket": "1억 미만",
            "employee_count_bracket": "5인 미만",
            "interests": "소상공인,판로개척",
        },
        "expect_keywords": ["소상공인", "음식", "부산", "판로"],
        "reject_keywords": ["수출기업", "반도체"],
    },
    {
        "name": "서울 제조업 중소기업 (10년차)",
        "profile": {
            "business_number": "TEST000004",
            "company_name": "정밀부품",
            "address_city": "서울",
            "establishment_date": "2016-05-20",
            "industry_code": "29111",  # 자동차 엔진용 부품 제조업
            "revenue_bracket": "10억~50억",
            "employee_count_bracket": "30인~50인",
            "interests": "기술개발,수출마케팅,정책자금",
        },
        "expect_keywords": ["제조", "수출", "기술", "자금", "중소기업"],
        "reject_keywords": ["소상공인", "예비창업"],
    },
    {
        "name": "대전 교육업 (학원)",
        "profile": {
            "business_number": "TEST000005",
            "company_name": "코딩아카데미",
            "address_city": "대전",
            "establishment_date": "2021-09-01",
            "industry_code": "85509",  # 기타 교육기관
            "revenue_bracket": "1억~5억",
            "employee_count_bracket": "5인~10인",
            "interests": "교육훈련,디지털전환",
        },
        "expect_keywords": ["교육", "디지털", "훈련"],
        "reject_keywords": ["수출기업", "반도체"],
    },
]


def evaluate_match_quality(test_case: dict) -> dict:
    """한 프로필에 대해 매칭 실행 및 품질 평가"""
    profile = test_case["profile"]
    matches = get_matches_for_user(profile)

    result = {
        "name": test_case["name"],
        "match_count": len(matches),
        "avg_score": 0,
        "top_score": 0,
        "relevant_hits": 0,
        "irrelevant_hits": 0,
        "details": [],
    }

    if not matches:
        return result

    scores = [m["match_score"] for m in matches]
    result["avg_score"] = sum(scores) / len(scores)
    result["top_score"] = max(scores)

    expect_kws = [kw.lower() for kw in test_case.get("expect_keywords", [])]
    reject_kws = [kw.lower() for kw in test_case.get("reject_keywords", [])]

    for m in matches:
        search_text = f"{m.get('title','')} {m.get('summary_text','')} {m.get('recommendation_reason','')}".lower()

        is_relevant = any(kw in search_text for kw in expect_kws)
        is_irrelevant = any(kw in search_text for kw in reject_kws)

        if is_relevant:
            result["relevant_hits"] += 1
        if is_irrelevant:
            result["irrelevant_hits"] += 1

        result["details"].append({
            "title": m.get("title", "")[:60],
            "score": m["match_score"],
            "reason": m.get("recommendation_reason", ""),
            "region": m.get("region", ""),
            "relevant": is_relevant,
            "irrelevant": is_irrelevant,
        })

    return result


def main():
    print("=" * 70)
    print("  MATCHING QUALITY TEST")
    print("=" * 70)

    all_results = []

    for tc in TEST_PROFILES:
        print(f"\n{'─'*70}")
        print(f"  Profile: {tc['name']}")
        print(f"  City={tc['profile']['address_city']} | KSIC={tc['profile']['industry_code']} | Rev={tc['profile']['revenue_bracket']} | Emp={tc['profile']['employee_count_bracket']}")
        print(f"  Interests: {tc['profile']['interests']}")
        print(f"{'─'*70}")

        result = evaluate_match_quality(tc)
        all_results.append(result)

        if result["match_count"] == 0:
            print("  [WARNING] No matches found!")
            continue

        relevance_rate = result["relevant_hits"] / result["match_count"] * 100 if result["match_count"] > 0 else 0
        irrelevant_rate = result["irrelevant_hits"] / result["match_count"] * 100 if result["match_count"] > 0 else 0

        print(f"  Results: {result['match_count']} matches | Avg Score: {result['avg_score']:.1f} | Top: {result['top_score']:.1f}")
        print(f"  Relevance: {result['relevant_hits']}/{result['match_count']} ({relevance_rate:.0f}%) | Irrelevant: {result['irrelevant_hits']}/{result['match_count']} ({irrelevant_rate:.0f}%)")

        # Top 5 결과 표시
        print(f"\n  Top 5 matches:")
        for i, d in enumerate(result["details"][:5], 1):
            flag = ""
            if d["relevant"]:
                flag += " [GOOD]"
            if d["irrelevant"]:
                flag += " [BAD]"
            print(f"    {i}. [{d['score']}] {d['title']}")
            print(f"       Reason: {d['reason']} | Region: {d['region']}{flag}")

    # Summary
    print(f"\n\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    total_matches = sum(r["match_count"] for r in all_results)
    total_relevant = sum(r["relevant_hits"] for r in all_results)
    total_irrelevant = sum(r["irrelevant_hits"] for r in all_results)

    for r in all_results:
        rel = r["relevant_hits"] / r["match_count"] * 100 if r["match_count"] > 0 else 0
        irr = r["irrelevant_hits"] / r["match_count"] * 100 if r["match_count"] > 0 else 0
        status = "PASS" if rel >= 30 and irr <= 20 else "WARN" if rel >= 20 else "FAIL"
        print(f"  [{status}] {r['name']}: {r['match_count']} matches, {rel:.0f}% relevant, {irr:.0f}% irrelevant")

    overall_rel = total_relevant / total_matches * 100 if total_matches > 0 else 0
    overall_irr = total_irrelevant / total_matches * 100 if total_matches > 0 else 0
    print(f"\n  Overall: {total_matches} matches, {overall_rel:.0f}% relevant, {overall_irr:.0f}% irrelevant")


if __name__ == "__main__":
    main()
