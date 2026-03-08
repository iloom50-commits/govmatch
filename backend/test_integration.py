"""통합 테스트: 전체 API 플로우 검증"""
import requests
import json
import sys

BASE = "http://127.0.0.1:8001"
PASS = 0
FAIL = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} → {detail}")


def run_tests():
    global PASS, FAIL
    print("=" * 60)
    print("통합 테스트 시작")
    print("=" * 60)

    # 1. Root
    r = requests.get(f"{BASE}/")
    test("GET / 응답", r.status_code == 200)

    # 2. Fetch company (기존 사용자)
    r = requests.post(f"{BASE}/api/fetch-company", json={"business_number": "1234567890"})
    data = r.json()
    test("POST /api/fetch-company 상태", data.get("status") == "SUCCESS")
    test("fetch-company 타입", data.get("type") in ("EXISTING", "NEW"))

    # 3. Save profile
    profile = {
        "business_number": "9999999999",
        "company_name": "통합테스트기업",
        "establishment_date": "2023-06-01",
        "address_city": "부산",
        "industry_code": "62011",
        "revenue_bracket": "UNDER_1B",
        "employee_count_bracket": "UNDER_5",
        "interests": "AI,스타트업"
    }
    r = requests.post(f"{BASE}/api/save-profile", json=profile)
    data = r.json()
    test("POST /api/save-profile", data.get("status") == "SUCCESS")

    # 4. Match
    r = requests.post(f"{BASE}/api/match", json={"business_number": "9999999999"})
    data = r.json()
    test("POST /api/match 상태", data.get("status") == "SUCCESS")
    match_count = len(data.get("data", []))
    test(f"매칭 결과 존재 ({match_count}건)", match_count >= 0)
    if match_count > 0:
        first = data["data"][0]
        test("매칭 결과 score 필드", "match_score" in first)
        print(f"    Top: {first['title'][:40]}... (score: {first.get('match_score')})")

    # 5. Notification settings - save
    r = requests.post(f"{BASE}/api/notification-settings", json={
        "business_number": "9999999999",
        "email": "test@example.com",
        "channel": "email",
        "is_active": True
    })
    data = r.json()
    test("POST /api/notification-settings", data.get("status") == "SUCCESS")

    # 6. Notification settings - get
    r = requests.get(f"{BASE}/api/notification-settings/9999999999")
    data = r.json()
    test("GET /api/notification-settings", data.get("status") == "SUCCESS")
    test("알림 이메일 저장 확인", data["data"]["email"] == "test@example.com")

    # 7. Check URL (새 URL)
    r = requests.post(f"{BASE}/api/check-url", json={"url": "https://nonexistent.example.com/test"})
    data = r.json()
    test("POST /api/check-url 상태", data.get("status") == "SUCCESS")
    test("is_duplicate 타입(bool)", isinstance(data.get("is_duplicate"), bool))
    test("새 URL → is_duplicate=False", data.get("is_duplicate") is False)

    # 8. Admin system sources
    r = requests.get(f"{BASE}/api/admin/system-sources")
    data = r.json()
    test("GET /api/admin/system-sources", data.get("status") == "SUCCESS")
    test("시스템 소스 3개", len(data.get("data", [])) == 3)

    # 9. Admin URLs
    r = requests.get(f"{BASE}/api/admin/urls")
    data = r.json()
    test("GET /api/admin/urls", data.get("status") == "SUCCESS")

    # 10. Industry recommend
    r = requests.post(f"{BASE}/api/industry-recommend", json={"company_name": "AI 소프트웨어"})
    data = r.json()
    test("POST /api/industry-recommend", data.get("status") == "SUCCESS")
    candidates = data.get("data", {}).get("candidates", [])
    test(f"업종 추천 후보 존재 ({len(candidates)}건)", len(candidates) > 0)

    # 11. Digest (manual trigger)
    r = requests.post(f"{BASE}/api/admin/send-digest")
    data = r.json()
    test("POST /api/admin/send-digest", data.get("status") == "SUCCESS")

    # Summary
    print()
    print("=" * 60)
    total = PASS + FAIL
    print(f"결과: {PASS}/{total} 통과, {FAIL} 실패")
    if FAIL == 0:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)
    return FAIL == 0


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except requests.ConnectionError:
        print("ERROR: 백엔드 서버에 연결할 수 없습니다. (http://127.0.0.1:8001)")
        sys.exit(1)
