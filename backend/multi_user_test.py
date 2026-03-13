# -*- coding: utf-8 -*-
import time, sqlite3, requests, sys
sys.stdout.reconfigure(encoding='utf-8')
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

BASE_API = "http://localhost:8002"
BASE_UI  = "http://localhost:3000"

TEST_USERS = [
    {
        "label": "서울 음식점 (소상공인)",
        "email": "tester_restaurant@test.com",
        "password": "test123456",
        "bn": "3001000001",
        "company_name": "서울 국수집",
        "establishment_date": "2021-03-15",
        "address_city": "서울",
        "industry_code": "56190",
        "revenue_bracket": "1억 미만",
        "employee_count_bracket": "5인 미만",
        "interests": "시설개선,고용지원,정책자금",
    },
    {
        "label": "경기 IT 스타트업",
        "email": "tester_it@test.com",
        "password": "test123456",
        "bn": "3001000002",
        "company_name": "테크랩스",
        "establishment_date": "2023-07-01",
        "address_city": "경기",
        "industry_code": "62010",
        "revenue_bracket": "1억~5억",
        "employee_count_bracket": "5인~10인",
        "interests": "기술개발,창업지원,디지털전환",
    },
    {
        "label": "부산 제조업 중소기업",
        "email": "tester_mfg@test.com",
        "password": "test123456",
        "bn": "3001000003",
        "company_name": "부산금속",
        "establishment_date": "2010-01-20",
        "address_city": "부산",
        "industry_code": "25990",
        "revenue_bracket": "10억~50억",
        "employee_count_bracket": "10인~30인",
        "interests": "기술개발,수출마케팅,고용지원",
    },
    {
        "label": "대전 미용실 (소상공인)",
        "email": "tester_beauty@test.com",
        "password": "test123456",
        "bn": "3001000004",
        "company_name": "헤어살롱 봄",
        "establishment_date": "2022-09-10",
        "address_city": "대전",
        "industry_code": "96110",
        "revenue_bracket": "1억 미만",
        "employee_count_bracket": "5인 미만",
        "interests": "시설개선,판로개척,정책자금",
    },
]

# DB 초기화
db_path = "c:/Users/osung/.gemini/antigravity/scratch/Auto_Gov_Macting/backend/gov_matching.db"
conn = sqlite3.connect(db_path)
for u in TEST_USERS:
    conn.execute("DELETE FROM users WHERE email = ? OR business_number = ?", (u["email"], u["bn"]))
conn.commit()
conn.close()

tokens = {}
print("=" * 60)
print("  다각도 매칭 적합성 테스트")
print("=" * 60)
print()

for u in TEST_USERS:
    r = requests.post(f"{BASE_API}/api/auth/register", json={
        "email": u["email"], "password": u["password"],
        "business_number": u["bn"], "company_name": u["company_name"]
    })
    if not r.ok:
        print(f"[!] 가입 실패: {u['label']} -> {r.json()}")
        continue
    token = r.json()["token"]
    tokens[u["bn"]] = token

    requests.post(f"{BASE_API}/api/save-profile", json={
        "business_number": u["bn"],
        "company_name": u["company_name"],
        "establishment_date": u["establishment_date"],
        "address_city": u["address_city"],
        "industry_code": u["industry_code"],
        "revenue_bracket": u["revenue_bracket"],
        "employee_count_bracket": u["employee_count_bracket"],
        "interests": u["interests"],
    }, headers={"Authorization": f"Bearer {token}"})

print(f"총 {len(TEST_USERS)}명 사용자 등록 및 프로필 저장 완료")
print()

# Selenium 브라우저 실행
opts = Options()
opts.add_argument("--window-size=1280,900")
opts.add_argument("--disable-blink-features=AutomationControlled")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])
driver = webdriver.Chrome(options=opts)
wait = WebDriverWait(driver, 15)

print("── 브라우저 UI 테스트 시작 ──")
print()

for idx, u in enumerate(TEST_USERS):
    print(f"[UI {idx+1}/{len(TEST_USERS)}] {u['label']}")
    print(f"  업종: {u['industry_code']} | 지역: {u['address_city']} | 관심: {u['interests']}")
    try:
        driver.get(BASE_UI)
        time.sleep(1)
        driver.execute_script("localStorage.clear()")
        token = tokens[u["bn"]]
        driver.execute_script(f"localStorage.setItem('auth_token', '{token}')")
        driver.refresh()

        # 매칭 결과 로딩 대기 (최대 12초)
        loaded = False
        for _ in range(12):
            time.sleep(1)
            try:
                cards = driver.find_elements(By.XPATH, "//h3[contains(@class,'font-black')]")
                if len(cards) >= 1:
                    loaded = True
                    break
            except:
                pass

        if not loaded:
            print("  [!] 매칭 결과 로딩 타임아웃")
            continue

        # 카드 제목 수집
        cards = driver.find_elements(By.XPATH, "//h3[contains(@class,'font-black')]")
        titles = [c.text.strip() for c in cards if c.text.strip()]

        # 탭 카운트 수집 (전체 탭 텍스트)
        tab_btns = driver.find_elements(By.XPATH,
            "//button[contains(@class,'rounded-lg') and contains(@class,'font-black') and contains(@class,'whitespace-nowrap')]")
        tabs_info = [t.text.strip() for t in tab_btns if t.text.strip()]

        print(f"  카드 수: {len(titles)}건 | 탭: {' / '.join(tabs_info[:6])}")
        for i, t in enumerate(titles[:5], 1):
            print(f"    {i}. {t[:52]}")
        if len(titles) > 5:
            print(f"    ... 외 {len(titles)-5}건")

    except Exception as e:
        print(f"  [오류] {e}")
    print()
    time.sleep(0.5)

driver.quit()

# API 레벨 매칭 적합성 검증
KEYWORD_MAP = {
    "3001000001": ["소상공인", "음식", "식당", "시설", "정책자금", "인테리어", "위생", "배달", "외식"],
    "3001000002": ["창업", "R&D", "기술", "IT", "소프트", "디지털", "스타트업", "벤처", "개발"],
    "3001000003": ["수출", "제조", "설비", "기계", "기술", "인력", "무역", "금속", "소재"],
    "3001000004": ["소상공인", "미용", "시설", "정책자금", "판로", "뷰티", "개인서비스"],
}

print("=" * 60)
print("  API 매칭 적합성 검증 결과")
print("=" * 60)
print()

total_relevant = 0
total_all = 0

for u in TEST_USERS:
    token = tokens.get(u["bn"])
    if not token:
        continue

    r = requests.post(f"{BASE_API}/api/match",
                      json={"business_number": u["bn"]},
                      headers={"Authorization": f"Bearer {token}"})
    matches = r.json().get("data", [])
    keywords = KEYWORD_MAP[u["bn"]]

    relevant, irrelevant = [], []
    for m in matches:
        combined = m.get("title","") + " " + m.get("recommendation_reason","") + " " + (m.get("summary_text") or "")
        if any(kw in combined for kw in keywords):
            relevant.append(m)
        else:
            irrelevant.append(m)

    scores = [m.get("match_score") or 0 for m in matches]
    avg_score = sum(scores)/len(scores) if scores else 0
    relevance_pct = len(relevant)/len(matches)*100 if matches else 0
    total_relevant += len(relevant)
    total_all += len(matches)

    verdict = "양호" if relevance_pct >= 30 else "주의"
    print(f"[{u['label']}]  [{verdict}]")
    print(f"  매칭 {len(matches)}건 | 평균점수 {avg_score:.0f} | 키워드 적합 {len(relevant)}/{len(matches)}건 ({relevance_pct:.0f}%)")

    if relevant:
        print(f"  적합 공고:")
        for m in relevant[:3]:
            print(f"    + {m['title'][:52]}")
    if irrelevant:
        print(f"  키워드 미매칭 공고 (일반 중소기업 공고일 수 있음):")
        for m in irrelevant[:2]:
            print(f"    - {m['title'][:52]}")
    print()

overall_pct = total_relevant/total_all*100 if total_all else 0
print(f"전체 적합도: {total_relevant}/{total_all}건 ({overall_pct:.0f}%)")
print()
print("=" * 60)
print("  테스트 완료")
print("=" * 60)
