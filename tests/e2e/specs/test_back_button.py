"""
PRO 전문가 대시보드 — 뒤로가기 단계별 복귀 테스트
실행: venv/Scripts/python test_back_button.py

검증 시나리오:
  A) Step1(상담종류) → Step2(고객유형) → Back → Step1 복귀
  B) Step1 → Step2 → Step3(고객정보폼) → Back×2 → Step1 복귀
  C) Step1 → Back → 모달 닫힘 (최초 화면에서 뒤로가기)
"""

import sys, io, time, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from selenium import webdriver
from selenium.webdriver.common.by import By

BASE = "http://localhost:3000"
API  = "http://localhost:8000"
EMAIL    = "pro_test@test.com"
PASSWORD = "Test1234!"


# ── 헬퍼 ─────────────────────────────────────────────────────────
def log(label, msg, ok=None):
    mark = "[PASS]" if ok is True else "[FAIL]" if ok is False else "[INFO]"
    print(f"  {mark} {label}: {msg}")

def body(driver):
    return driver.find_element(By.TAG_NAME, "body").text

def click_text(driver, *texts):
    """texts 중 하나라도 포함하는 표시된 버튼 클릭"""
    btns = driver.find_elements(By.TAG_NAME, "button")
    for b in btns:
        if not b.is_displayed():
            continue
        t = b.text.strip()
        if any(kw in t for kw in texts):
            b.click()
            return True
    return False

def back(driver):
    driver.execute_script("window.history.back()")
    time.sleep(1.8)

def get_token():
    r = requests.post(f"{API}/api/auth/login",
                      json={"email": EMAIL, "password": PASSWORD}, timeout=5)
    return r.json().get("token", "")

def open_pro_dashboard(driver, token):
    """로그인 → 플로팅 버튼 클릭 → PRO 대시보드 열기"""
    driver.get(BASE)
    time.sleep(2)
    driver.execute_script(f'localStorage.setItem("auth_token", "{token}");')
    driver.refresh()
    time.sleep(3)

    # JS로 AI 챗봇 오픈 이벤트 직접 발송 (플로팅 버튼 위치 의존 제거)
    driver.execute_script("window.dispatchEvent(new CustomEvent('open-ai-chatbot'));")
    time.sleep(2)

    # 이벤트가 없으면 플로팅 버튼 직접 클릭 시도
    if "전문가 대시보드" not in body(driver) and "어떤 상담" not in body(driver):
        vw = driver.execute_script("return window.innerWidth")
        vh = driver.execute_script("return window.innerHeight")
        btns = driver.find_elements(By.TAG_NAME, "button")
        float_btn = next(
            (b for b in btns
             if b.is_displayed() and b.rect["x"] > vw * 0.7 and b.rect["y"] > vh * 0.5),
            None,
        )
        if float_btn:
            float_btn.click()
            time.sleep(2)

    return "전문가 대시보드" in body(driver) or "어떤 상담" in body(driver)

def reset_to_step1(driver, token):
    """PRO 대시보드를 닫고 다시 열어 Step1 초기 상태로 복귀"""
    # X 버튼으로 닫기
    close_btns = driver.find_elements(By.XPATH, "//*[@title='닫기' or @aria-label='닫기']")
    for b in close_btns:
        if b.is_displayed():
            b.click()
            time.sleep(1)
            break
    # 다시 열기
    return open_pro_dashboard(driver, token)


# ── 시나리오 A: Step2 → Back → Step1 ─────────────────────────────
def scenario_a(driver, results):
    print("\n[시나리오 A] Step2 → 뒤로가기 → Step1 복귀")

    # Step1: 지원사업 상담 선택
    ok = click_text(driver, "지원사업 상담")
    log("Step1 클릭", "지원사업 상담", ok=ok)
    time.sleep(1)

    # Step2 도착 확인
    at_step2 = "고객 유형" in body(driver) or "유형을 선택" in body(driver)
    log("Step2 도착", str(at_step2), ok=at_step2)
    results.append(at_step2)
    if not at_step2:
        return

    # 브라우저 뒤로가기
    back(driver)
    at_step1 = "어떤 상담" in body(driver) or "지원사업 상담" in body(driver)
    log("Back → Step1 복귀", str(at_step1), ok=at_step1)
    results.append(at_step1)


# ── 시나리오 B: Step3 → Back×2 → Step1 ──────────────────────────
def scenario_b(driver, token, results):
    print("\n[시나리오 B] Step3(폼) → Back×2 → Step1 복귀")

    reset_to_step1(driver, token)
    time.sleep(0.5)

    click_text(driver, "지원사업 상담"); time.sleep(1)
    click_text(driver, "사업자"); time.sleep(1)

    at_step3 = "기업명" in body(driver) or "설립연도" in body(driver) or "고객 정보" in body(driver)
    log("Step3 폼 도착", str(at_step3), ok=at_step3)
    results.append(at_step3)
    if not at_step3:
        return

    back(driver)
    txt2 = body(driver)
    at_step2 = "고객 유형" in txt2 or "유형을 선택" in txt2 or "사업자" in txt2 and "기업명" not in txt2
    log("Back1 → Step2 복귀", str(at_step2), ok=at_step2)
    if not at_step2:
        log("  현재 화면", txt2[:100], ok=None)
    results.append(at_step2)

    back(driver)
    txt1 = body(driver)
    at_step1 = "어떤 상담" in txt1 or "지원사업 상담" in txt1
    log("Back2 → Step1 복귀", str(at_step1), ok=at_step1)
    if not at_step1:
        log("  현재 화면", txt1[:100], ok=None)
    results.append(at_step1)


# ── 시나리오 C: Step1 → Back → 모달 닫힘 ────────────────────────
def scenario_c(driver, token, results):
    print("\n[시나리오 C] Step1(초기화면) → 뒤로가기 → 모달 닫힘")

    reset_to_step1(driver, token)
    time.sleep(0.5)

    # Step1에서 바로 뒤로가기
    back(driver)
    modal_closed = "전문가 대시보드" not in body(driver)
    log("모달 닫힘", str(modal_closed), ok=modal_closed)
    results.append(modal_closed)
    log("최종 URL", driver.current_url, ok=None)


# ── 메인 ────────────────────────────────────────────────────────
def main():
    print("=== PRO 뒤로가기 단계 복귀 테스트 ===\n")

    token = get_token()
    if not token:
        print("[ERROR] 로그인 실패 — 백엔드 서버 확인 필요")
        return

    opts = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=opts)
    results = []

    try:
        ok = open_pro_dashboard(driver, token)
        log("PRO 대시보드 열기", str(ok), ok=ok)
        if not ok:
            print("[ERROR] PRO 대시보드 열기 실패")
            return

        scenario_a(driver, results)
        scenario_b(driver, token, results)
        scenario_c(driver, token, results)

    finally:
        passed = sum(1 for r in results if r)
        failed = sum(1 for r in results if not r)
        total  = len(results)
        print(f"\n{'='*40}")
        print(f"결과: {passed}/{total} 통과" +
              (f"  [{failed}개 실패]" if failed else "  [모두 통과]"))
        time.sleep(2)
        driver.quit()


if __name__ == "__main__":
    main()
