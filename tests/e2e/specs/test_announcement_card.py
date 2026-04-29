"""
PRO 매칭 공고 카드 테스트
- 시나리오 A: 제목 클릭 시 새 탭으로 원본 URL 이동
- 시나리오 B: '상담 →' 버튼 클릭 시 상담 시작
- 시나리오 C: 금액 표기 — 숫자 형식(200,000,000원) 없는지 확인

실행: venv/Scripts/python test_announcement_card.py
"""
import sys, io, time, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE  = "http://localhost:3000"
API   = "http://localhost:8000"
EMAIL = "pro_test@test.com"
PW    = "Test1234!"


def log(label, msg, ok=None):
    mark = "[PASS]" if ok is True else "[FAIL]" if ok is False else "[INFO]"
    print(f"  {mark} {label}: {msg}")

def body(driver):
    return driver.find_element(By.TAG_NAME, "body").text

def get_token():
    r = requests.post(f"{API}/api/auth/login",
                      json={"email": EMAIL, "password": PW}, timeout=5)
    return r.json().get("token", "")

def open_pro_dashboard(driver, token):
    driver.get(BASE)
    time.sleep(2)
    driver.execute_script(f'localStorage.setItem("auth_token", "{token}");')
    driver.refresh()
    time.sleep(3)
    driver.execute_script("window.dispatchEvent(new CustomEvent('open-ai-chatbot'));")
    time.sleep(2)
    return "전문가 대시보드" in body(driver) or "어떤 상담" in body(driver)

def click_btn_with_text(driver, *texts):
    """표시된 버튼 중 texts 중 하나를 포함하는 버튼 클릭"""
    btns = driver.find_elements(By.TAG_NAME, "button")
    for b in btns:
        if not b.is_displayed():
            continue
        t = b.text.strip()
        if any(kw in t for kw in texts):
            b.click()
            return t
    return None

def close_overlays(driver):
    """알림 팝업 등 오버레이 닫기"""
    # ✕ 또는 닫기 버튼 클릭
    try:
        close_btns = driver.find_elements(By.XPATH, "//*[text()='✕' or text()='×' or @aria-label='닫기' or @title='닫기']")
        for b in close_btns:
            if b.is_displayed():
                b.click()
                time.sleep(0.5)
    except:
        pass
    # ESC 키로 팝업 닫기
    from selenium.webdriver.common.keys import Keys
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.3)
    except:
        pass

def go_to_step1_and_match(driver):
    """지원사업 상담 → 사업자 선택 → 폼 기본값 제출 → 매칭 결과 대기"""
    # Step1: 지원사업 상담
    clicked = click_btn_with_text(driver, "지원사업 상담")
    log("Step1 클릭", str(clicked), ok=bool(clicked))
    time.sleep(1.5)

    # Step2: 고객 유형 (사업자)
    clicked = click_btn_with_text(driver, "사업자", "법인사업자", "개인사업자")
    log("Step2 클릭", str(clicked), ok=bool(clicked))
    time.sleep(2)

    # Step3: ProfileInputForm 스크린샷 확인 후 건너뛰기 클릭
    time.sleep(1.5)
    driver.save_screenshot("step3_form.png")
    log("스크린샷", "step3_form.png 저장", ok=None)

    # JS로 "건너뛰고 바로 상담하기" 클릭 (.click() — React 이벤트 트리거용)
    result = driver.execute_script("""
        var btns = document.querySelectorAll('button');
        for(var i=0; i<btns.length; i++){
            var t = btns[i].textContent;
            if(t.includes('건너뛰고 바로 상담하기') || t.trim() === '상담 시작'){
                btns[i].scrollIntoView({block:'center'});
                btns[i].click();
                return t.trim().substring(0, 30);
            }
        }
        return null;
    """)
    clicked = result
    log("Step3 폼 제출(JS)", str(clicked), ok=bool(clicked))
    time.sleep(1)

    # 브라우저 콘솔 에러 캡처
    time.sleep(2)
    logs = driver.get_log("browser")
    errors = [l for l in logs if l["level"] in ("SEVERE", "WARNING")]
    if errors:
        print("  [DEBUG] 브라우저 콘솔 에러:")
        for e in errors[:5]:
            print(f"    [{e['level']}] {e['message'][:120]}")

    # localStorage의 auth_token 확인
    tok_in_storage = driver.execute_script("return localStorage.getItem('auth_token')")
    log("auth_token 확인", tok_in_storage[:20] + "..." if tok_in_storage else "없음!", ok=bool(tok_in_storage))

    # 현재 ProSecretary 상태 JS로 확인
    pro_text = driver.execute_script("""
        var els = document.querySelectorAll('[class*="rounded-xl"]');
        var texts = [];
        for(var i=0; i<els.length; i++){
            var t = els[i].innerText;
            if(t && t.length > 5 && t.length < 200) texts.push(t.substring(0, 80));
        }
        return texts.slice(0, 10).join(' | ');
    """)
    print(f"  [DEBUG] 카드 영역 텍스트: {str(pro_text)[:300]}")

    def get_all_text():
        """body.text + fixed/absolute 요소 텍스트까지 JS로 수집"""
        return driver.execute_script("""
            return Array.from(document.querySelectorAll('*'))
                .filter(el => {
                    var s = window.getComputedStyle(el);
                    return (s.position === 'fixed' || s.position === 'absolute') && el.innerText && el.innerText.length > 10;
                })
                .map(el => el.innerText.substring(0, 200))
                .join('\\n---\\n');
        """)

    # 매칭 결과 대기 (최대 60초) — fixed 레이어 포함 검색
    print("  [INFO] AI 매칭 대기 중 (최대 60초)...")
    MATCH_KEYWORDS = ["신청 가능", "마감 임박", "관심 일치", "참고", "interest_match"]
    for i in range(60):
        time.sleep(1)
        full_pg = body(driver) + "\n" + (get_all_text() or "")
        if any(kw in full_pg for kw in MATCH_KEYWORDS):
            log("매칭 결과 수신", f"{i+1}초 후", ok=True)
            return True
        if i == 14:
            overlay = get_all_text() or ""
            print(f"  [DEBUG] fixed 레이어(15초):\n{overlay[:500]}")
    # 최종 화면 덤프
    overlay = get_all_text() or ""
    print(f"  [DEBUG] 최종 fixed 레이어:\n{overlay[:600]}")
    return False


def scenario_a_title_link(driver, results):
    """제목 클릭 → 새 탭으로 원본 URL 이동"""
    print("\n[시나리오 A] 공고 제목 클릭 → 새 탭 원본 URL 이동")

    # <a> 태그로 된 제목 링크 찾기
    links = driver.find_elements(By.TAG_NAME, "a")
    title_link = None
    for a in links:
        if not a.is_displayed():
            continue
        href = a.get_attribute("href") or ""
        target = a.get_attribute("target") or ""
        text = a.text.strip()
        # 공고 제목 링크: href가 http로 시작하고 target=_blank, 텍스트가 있는 것
        if href.startswith("http") and target == "_blank" and len(text) > 5:
            title_link = a
            log("링크 발견", f"{text[:30]}... → {href[:60]}", ok=True)
            break

    if not title_link:
        log("링크 발견", "origin_url을 가진 <a> 링크 없음 — 아직 구 데이터이거나 URL 없는 공고", ok=False)
        results.append(False)
        return

    # 새 탭 열림 확인
    original_handles = set(driver.window_handles)
    title_link.click()
    time.sleep(2)
    new_handles = set(driver.window_handles) - original_handles
    opened_new_tab = len(new_handles) > 0
    log("새 탭 오픈", str(opened_new_tab), ok=opened_new_tab)
    results.append(opened_new_tab)

    if new_handles:
        driver.switch_to.window(list(new_handles)[0])
        new_url = driver.current_url
        log("이동된 URL", new_url[:80], ok=None)
        is_external = not new_url.startswith("http://localhost")
        log("외부 URL", str(is_external), ok=is_external)
        results.append(is_external)
        driver.close()
        driver.switch_to.window(list(original_handles)[0])


def scenario_b_consult_button(driver, results):
    """'상담 →' 버튼 클릭 → AI 상담 시작"""
    print("\n[시나리오 B] '상담 →' 버튼 클릭 → 상담 시작")

    btns = driver.find_elements(By.TAG_NAME, "button")
    consult_btn = None
    for b in btns:
        if b.is_displayed() and "상담" in b.text and "→" in b.text:
            consult_btn = b
            break

    if not consult_btn:
        log("'상담 →' 버튼 발견", "없음", ok=False)
        results.append(False)
        return

    log("'상담 →' 버튼 발견", "있음", ok=True)
    consult_btn.click()
    time.sleep(4)

    pg = body(driver)
    # 상담 시작되면 분석 중이거나 메시지가 나타남
    started = ("분석" in pg or "공고를" in pg or "AI" in pg or "답변" in pg
               or "섹션" in pg or "지원" in pg and "가능" not in pg)
    log("상담 시작 여부", str(started), ok=started)
    results.append(started)


def scenario_c_amount_format(driver, results):
    """금액 표기 통일: 숫자 나열 형식(200,000,000원) 없는지 확인"""
    print("\n[시나리오 C] 금액 표기 — 숫자 나열 형식 없는지 확인")

    pg = body(driver)
    # 9자리 이상 숫자 콤마 형식 (예: 200,000,000) 검출
    import re
    raw_amounts = re.findall(r'\d{1,3}(?:,\d{3}){2,}원', pg)
    no_raw = len(raw_amounts) == 0
    if raw_amounts:
        log("숫자 나열 형식 발견", str(raw_amounts[:3]), ok=False)
    else:
        log("숫자 나열 형식 없음", "모두 억/만원 단위로 표기됨", ok=True)
    results.append(no_raw)

    # 억/만원 형식 확인
    korean_amounts = re.findall(r'\d+억\s*\d*만?원?|\d+만원', pg)
    log("한국어 단위 금액", str(korean_amounts[:5]) if korean_amounts else "없음", ok=None)


def main():
    print("=== PRO 공고 카드 테스트 ===\n")

    token = get_token()
    if not token:
        print("[ERROR] 로그인 실패")
        return

    opts = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=opts)
    results = []

    try:
        ok = open_pro_dashboard(driver, token)
        log("PRO 대시보드 오픈", str(ok), ok=ok)
        if not ok:
            print("[ERROR] PRO 대시보드 오픈 실패")
            return

        matched = go_to_step1_and_match(driver)
        log("매칭 결과 수신", str(matched), ok=matched)
        if not matched:
            print("[WARN] 매칭 결과를 받지 못함 — 테스트 중단")
            return

        scenario_c_amount_format(driver, results)
        scenario_a_title_link(driver, results)
        scenario_b_consult_button(driver, results)

    finally:
        passed = sum(1 for r in results if r)
        failed = sum(1 for r in results if not r)
        total  = len(results)
        print(f"\n{'='*40}")
        print(f"결과: {passed}/{total} 통과" +
              (f"  [{failed}개 실패]" if failed else "  [모두 통과]"))
        time.sleep(3)
        driver.quit()


if __name__ == "__main__":
    main()
