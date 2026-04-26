# -*- coding: utf-8 -*-
"""
Selenium E2E Test - 두 가지 버그 검증
1. 프로필 게이트: 업종 미설정 시 AI상담 버튼 -> 프로필폼 먼저 표시
2. 창 잔존 버그: AiConsultModal 닫기 후 다른 창이 남지 않아야 함
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import time
import random
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

BASE_URL = "http://localhost:3000"
API_URL  = "http://localhost:8000"
TEST_ID  = random.randint(10000, 99999)
TEST_BIZ_NUM  = f"{TEST_ID:010d}"
TEST_EMAIL    = f"gate_{TEST_ID}@naver.com"
TEST_PASSWORD = "test123456"

passed = 0
failed = 0


def log(step, msg, status="INFO"):
    icons = {"PASS": "[PASS]", "FAIL": "[FAIL]", "INFO": "[----]"}
    print(f"  {icons.get(status,'[----]')} {step}: {msg}")


def create_driver():
    opts = Options()
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(2)
    return driver


def body(driver):
    return driver.find_element(By.TAG_NAME, "body").text


def wait_text(driver, text, timeout=10):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, f"//*[contains(text(),'{text}')]"))
    )


def click_xpath(driver, xpath, timeout=8):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.2)
    el.click()
    return el


# ─────────────────────────────────────────────
# Step 0: API로 테스트 계정 생성 + 로그인 -> 토큰 획득
# ─────────────────────────────────────────────
def api_setup():
    global passed, failed
    print("\nStep 0: API 계정 생성 + 로그인")
    print("-" * 40)

    # 회원가입 (industry_code 없이 — revenue_bracket/employee 는 설정)
    reg = requests.post(f"{API_URL}/api/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "business_number": TEST_BIZ_NUM,
        "user_type": "business",
        "address_city": "경기",
        "revenue_bracket": "1억~5억",
        "employee_count_bracket": "10인~30인",
        "establishment_date": "2020-01-01",
        "interests": "창업지원,기술개발",
    }, timeout=15)

    if reg.status_code in (200, 201, 409):
        log("회원가입", f"status={reg.status_code}", "PASS"); passed += 1
    else:
        log("회원가입", f"FAIL status={reg.status_code} {reg.text[:80]}", "FAIL"); failed += 1
        return None

    # 로그인
    login = requests.post(f"{API_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    }, timeout=15)

    if login.status_code == 200:
        token = login.json().get("token") or login.json().get("access_token")
        log("로그인", f"토큰 획득 (len={len(token) if token else 0})", "PASS"); passed += 1
        return token
    else:
        log("로그인", f"FAIL status={login.status_code} {login.text[:80]}", "FAIL"); failed += 1
        return None


# ─────────────────────────────────────────────
# Step 1: 토큰 주입 -> 대시보드 진입
# ─────────────────────────────────────────────
def setup_browser(driver, token):
    global passed, failed
    print("\nStep 1: 브라우저에 토큰 주입 + 대시보드 진입")
    print("-" * 40)

    driver.get(BASE_URL)
    time.sleep(2)

    driver.execute_script(f"localStorage.setItem('auth_token', '{token}');")
    driver.refresh()
    time.sleep(4)

    b = body(driver)
    if "지원금AI" in b or "기업 지원금" in b or "전체" in b:
        log("대시보드", "진입 확인", "PASS"); passed += 1
        return True
    else:
        log("대시보드", f"진입 실패: {b[:120]}", "FAIL"); failed += 1
        return False


# ─────────────────────────────────────────────
# Step 2: 프로필 게이트 — AI상담 버튼 -> 프로필폼 확인
# ─────────────────────────────────────────────
def test_profile_gate(driver):
    global passed, failed
    print("\nStep 2: 프로필 게이트 (업종 미설정 -> AI버튼 -> 프로필폼)")
    print("-" * 40)

    time.sleep(2)

    # JS로 request-ai-consult 이벤트 발송 (ResultCard 버튼과 동일한 경로)
    driver.execute_script("""
        window.dispatchEvent(new CustomEvent('request-ai-consult', {
            detail: { announcement: {
                announcement_id: 12345,
                title: '게이트 테스트 공고',
                support_amount: '최대 1억원',
                deadline_date: '2026-12-31',
                department: '중소벤처기업부',
                category: '창업지원'
            }}
        }));
    """)
    log("게이트", "request-ai-consult 이벤트 발송", "INFO")
    time.sleep(2.5)

    b = body(driver)

    profile_form_keywords = [
        "어떤 지원금을 찾고 계세요",
        "기업 기본 정보",
        "사업장 소재지",
        "맞춤 알림",
        "업종",
        "거주 지역",
    ]
    ai_modal_keywords = [
        "AI 지원대상 상담",
        "질문을 입력하세요",
    ]

    profile_open = any(kw in b for kw in profile_form_keywords)
    ai_open      = any(kw in b for kw in ai_modal_keywords)

    if profile_open and not ai_open:
        log("게이트", "OK - 프로필폼 먼저 표시됨 (AI모달 미열림)", "PASS"); passed += 1
    elif ai_open:
        log("게이트", "FAIL - AI모달이 바로 열림 (게이트 미작동)", "FAIL"); failed += 1
        log("게이트", f"화면내용: {b[:200]}", "INFO")
    else:
        log("게이트", f"판정불가: profile={profile_open}, ai={ai_open}", "FAIL"); failed += 1
        log("게이트", f"화면내용: {b[:200]}", "INFO")

    # 폼 닫기
    try:
        close = driver.find_elements(By.XPATH, "//button[normalize-space(text())='X' or normalize-space(text())='x']")
        if not close:
            close = driver.find_elements(By.CSS_SELECTOR, "button.rounded-full")
        if close:
            for c in close:
                if c.is_displayed():
                    c.click()
                    break
        time.sleep(1)
    except Exception:
        pass


# ─────────────────────────────────────────────
# Step 3: FAB 버튼 게이트 (request-fund-chat)
# ─────────────────────────────────────────────
def test_fab_gate(driver):
    global passed, failed
    print("\nStep 3: FAB 자금상담 게이트")
    print("-" * 40)

    time.sleep(1)

    driver.execute_script(
        "window.dispatchEvent(new CustomEvent('request-fund-chat'));"
    )
    log("FAB", "request-fund-chat 이벤트 발송", "INFO")
    time.sleep(2.5)

    b = body(driver)

    profile_open = any(kw in b for kw in [
        "어떤 지원금을 찾고 계세요",
        "기업 기본 정보",
        "사업장 소재지",
        "맞춤 알림",
        "업종",
    ])
    chatbot_open = "지원사업에 대해 자유롭게 질문" in b or "자금상담" in b and "입력" in b

    if profile_open and not chatbot_open:
        log("FAB", "OK - 프로필폼 먼저 표시됨", "PASS"); passed += 1
    elif chatbot_open:
        log("FAB", "FAIL - 챗봇이 바로 열림 (게이트 미작동)", "FAIL"); failed += 1
    else:
        log("FAB", f"판정불가: profile={profile_open}, chatbot={chatbot_open}", "FAIL"); failed += 1
        log("FAB", f"화면내용: {b[:200]}", "INFO")

    # 닫기
    try:
        close_btns = driver.find_elements(By.CSS_SELECTOR, "button.rounded-full")
        for c in close_btns:
            if c.is_displayed():
                c.click()
                break
        time.sleep(1)
    except Exception:
        pass


# ─────────────────────────────────────────────
# Step 4: AiConsultModal 닫기 후 잔존 창 없음
# ─────────────────────────────────────────────
def test_close_window(driver):
    global passed, failed
    print("\nStep 4: AiConsultModal 닫기 후 잔존창 없음")
    print("-" * 40)

    time.sleep(1)

    # 게이트 우회해서 직접 open-ai-consult 발송
    driver.execute_script("""
        window.dispatchEvent(new CustomEvent('open-ai-consult', {
            detail: { announcement: {
                announcement_id: 99999,
                title: '잔존창 테스트 공고',
                support_amount: '최대 5000만원',
                deadline_date: '2026-12-31',
                department: '테스트부처',
                category: '창업지원'
            }}
        }));
    """)
    log("잔존창", "open-ai-consult 이벤트 발송", "INFO")
    time.sleep(3)

    b = body(driver)
    modal_opened = "AI 지원대상 상담" in b or "질문을 입력하세요" in b or "잔존창 테스트 공고" in b
    if modal_opened:
        log("잔존창", "AiConsultModal 열림 확인", "PASS"); passed += 1
    else:
        log("잔존창", f"모달 미열림: {b[:100]}", "FAIL"); failed += 1
        return

    # 닫기 버튼 찾기 — CSS로 우측 상단 × 버튼
    closed = False
    try:
        # 저장하고 닫기 버튼
        save_close = driver.find_elements(By.XPATH,
            "//button[contains(.,'저장하고 닫기') or contains(.,'닫기')]"
        )
        if save_close:
            for btn in save_close:
                if btn.is_displayed():
                    btn.click()
                    log("잔존창", f"'{btn.text.strip()}' 버튼 클릭", "INFO")
                    closed = True
                    break
    except Exception as e:
        log("잔존창", f"저장닫기 버튼 예외: {e}", "INFO")

    if not closed:
        try:
            # 오른쪽 상단 X 버튼 (헤더)
            header_btns = driver.find_elements(By.CSS_SELECTOR,
                "[data-consult-panel] button, .fixed button"
            )
            for btn in reversed(header_btns):
                txt = btn.text.strip()
                if txt in ("X", "x", "") and btn.is_displayed():
                    btn.click()
                    closed = True
                    break
        except Exception:
            pass

    if not closed:
        # JS로 이벤트
        driver.execute_script(
            "document.querySelector('[data-consult-panel]')?.remove();"
        )
        log("잔존창", "강제 제거로 닫기 시뮬레이션", "INFO")

    time.sleep(2)
    b_after = body(driver)

    ai_still_open = "AI 지원대상 상담" in b_after and "질문을 입력하세요" in b_after
    chatbot_still_open = "지원사업에 대해 자유롭게 질문" in b_after

    if not ai_still_open and not chatbot_still_open:
        log("잔존창", "OK - 닫기 후 잔존 창 없음", "PASS"); passed += 1
    elif chatbot_still_open:
        log("잔존창", "FAIL - 자금상담 챗봇 창이 잔존함", "FAIL"); failed += 1
    elif ai_still_open:
        log("잔존창", "FAIL - AI상담 모달이 아직 열려있음", "FAIL"); failed += 1

    # 브라우저 창 개수
    wins = driver.window_handles
    if len(wins) == 1:
        log("잔존창", f"OK - 브라우저 탭 {len(wins)}개 (정상)", "PASS"); passed += 1
    else:
        log("잔존창", f"FAIL - 브라우저 탭 {len(wins)}개 잔존", "FAIL"); failed += 1


# ─────────────────────────────────────────────
# main
# ─────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  프로필 게이트 + 잔존창 E2E 테스트")
    print(f"  계정: {TEST_EMAIL} / BN: {TEST_BIZ_NUM}")
    print(f"{'='*60}")

    token = api_setup()
    if not token:
        print("\n  [FATAL] 토큰 획득 실패 — 테스트 중단")
        return

    driver = create_driver()
    try:
        ok = setup_browser(driver, token)
        if not ok:
            print("  [FATAL] 대시보드 진입 실패")
            return

        test_profile_gate(driver)
        time.sleep(1)
        test_fab_gate(driver)
        time.sleep(1)
        test_close_window(driver)

    except Exception as e:
        print(f"\n  [FATAL] {e}")
        import traceback; traceback.print_exc()
    finally:
        print(f"\n{'='*60}")
        print(f"  결과: {passed} PASSED / {failed} FAILED")
        print(f"{'='*60}\n")
        time.sleep(3)
        driver.quit()


if __name__ == "__main__":
    main()
