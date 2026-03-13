"""
Selenium E2E Test: 온보딩 → 대시보드 → 로그아웃 → 로그인 전체 플로우 테스트
(이메일: 아이디 + @ + 도메인 선택 UI)
"""

import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

BASE_URL = "http://localhost:3000"
TEST_EMAIL_ID = f"test_{random.randint(10000,99999)}"
TEST_EMAIL_DOMAIN = "naver.com"
TEST_EMAIL = f"{TEST_EMAIL_ID}@{TEST_EMAIL_DOMAIN}"
TEST_PASSWORD = "test123456"


def log(step, msg, status="INFO"):
    icons = {"PASS": "[PASS]", "FAIL": "[FAIL]", "INFO": "[----]", "WAIT": "[....]"}
    print(f"  {icons.get(status, '[----]')} {step}: {msg}")


def create_driver():
    opts = Options()
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(3)
    return driver


def wait_and_click(driver, xpath, timeout=10):
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.3)
    el.click()
    return el


def wait_for_text(driver, text, timeout=10):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{text}')]"))
    )


def set_react_input(driver, selector, value):
    driver.execute_script("""
        const el = document.querySelector(arguments[0]);
        if (!el) return;
        const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        nativeSetter.call(el, arguments[1]);
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('input', { bubbles: true }));
    """, selector, value)
    time.sleep(0.3)


def fill_email(driver, email_id, domain="naver.com"):
    """아이디 + @ + 도메인 선택 UI에 이메일 입력"""
    id_input = driver.find_element(By.XPATH, "//input[@placeholder='아이디']")
    id_input.clear()
    id_input.send_keys(email_id)

    select_el = driver.find_element(By.TAG_NAME, "select")
    Select(select_el).select_by_value(domain)
    time.sleep(0.3)


def clear_local_storage(driver):
    driver.execute_script("localStorage.clear();")
    driver.refresh()


def test_full_flow():
    driver = create_driver()
    passed = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"  Selenium E2E 테스트 시작")
    print(f"  테스트 이메일: {TEST_EMAIL}")
    print(f"{'='*60}\n")

    try:
        # =============================================
        # Phase 1: 온보딩 플로우 (신규 사용자)
        # =============================================
        print("Phase 1: 온보딩 플로우 (신규 사용자)")
        print("-" * 40)

        driver.get(BASE_URL)
        clear_local_storage(driver)
        time.sleep(3)

        wait_for_text(driver, "기업 기본정보를 알려주세요", timeout=15)
        log("Step 1", "온보딩 첫 화면 로드 확인", "PASS"); passed += 1

        wait_and_click(driver, "//button[contains(., '개인사업자')]")
        log("Step 1", "개인사업자 선택", "PASS"); passed += 1
        time.sleep(0.8)

        set_react_input(driver, "input[type='date']", "2020-05-15")
        log("Step 1", "설립일 입력: 2020-05-15", "PASS"); passed += 1

        wait_and_click(driver, "//button[text()='서울']")
        log("Step 1", "소재지 '서울' 선택", "PASS"); passed += 1
        time.sleep(0.3)

        wait_and_click(driver, "//button[contains(., '다음 단계로')]")
        time.sleep(1.5)

        body_text = driver.find_element(By.TAG_NAME, "body").text
        if "관심 분야를 알려주세요" in body_text:
            log("Step 1→2", "Step 2 전환 성공", "PASS"); passed += 1
        else:
            driver.execute_script("""
                const inputs = document.querySelectorAll("input[type='date']");
                const textIn = document.querySelectorAll("input[placeholder='YYYY-MM-DD']");
                const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                if (inputs[0]) { setter.call(inputs[0], '2020-05-15'); inputs[0].dispatchEvent(new Event('change', {bubbles:true})); }
                if (textIn[0]) { setter.call(textIn[0], '2020-05-15'); textIn[0].dispatchEvent(new Event('change', {bubbles:true})); }
            """)
            time.sleep(0.5)
            wait_and_click(driver, "//button[contains(., '다음 단계로')]")
            time.sleep(1.5)
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "관심 분야를 알려주세요" in body_text:
                log("Step 1→2", "재시도로 Step 2 전환 성공", "PASS"); passed += 1
            else:
                log("Step 1→2", f"전환 실패: {body_text[:80]}", "FAIL"); failed += 1
                raise Exception("Step 2 전환 실패")

        # ---- Step 2 ----
        interest_buttons = driver.find_elements(
            By.XPATH, "//div[contains(@class,'grid')]//button[contains(@class,'rounded-2xl')]"
        )
        for btn in interest_buttons[:3]:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            time.sleep(0.2)
            btn.click()
        log("Step 2", "관심 분야 3개 선택", "PASS"); passed += 1

        wait_and_click(driver, "//button[contains(., '다음 단계로')]")
        time.sleep(1)

        # ---- Step 3 ----
        wait_for_text(driver, "기업 규모를 알려주세요", timeout=10)
        log("Step 3", "기업 규모 화면 도달", "PASS"); passed += 1

        wait_and_click(driver, "//button[contains(text(), '1억 미만')]")
        wait_and_click(driver, "//button[contains(text(), '5인 미만')]")
        log("Step 3", "매출/직원 선택 완료", "PASS"); passed += 1

        wait_and_click(driver, "//button[contains(., '다음 단계로')]")
        time.sleep(1)

        # ---- Step 4 ----
        wait_for_text(driver, "업종을 선택해 주세요", timeout=10)
        code_input = driver.find_element(By.XPATH, "//input[@placeholder='업종 코드 직접 입력 (5자리)']")
        code_input.clear()
        code_input.send_keys("56101")
        time.sleep(0.5)
        log("Step 4", "업종 코드 '56101' 입력", "PASS"); passed += 1

        wait_and_click(driver, "//button[contains(., '다음 단계로')]")
        time.sleep(1)

        # ---- Step 5: 이메일(아이디+도메인) / 비밀번호 ----
        wait_for_text(driver, "맞춤 매칭 결과를 받아보세요", timeout=10)
        log("Step 5", "이메일/비밀번호 화면 도달", "PASS"); passed += 1

        fill_email(driver, TEST_EMAIL_ID, TEST_EMAIL_DOMAIN)
        log("Step 5", f"이메일 입력: {TEST_EMAIL_ID} @ {TEST_EMAIL_DOMAIN}", "PASS"); passed += 1

        pw_input = driver.find_element(By.XPATH, "//input[@type='password']")
        pw_input.clear()
        pw_input.send_keys(TEST_PASSWORD)
        log("Step 5", "비밀번호 입력 완료", "PASS"); passed += 1

        wait_and_click(driver, "//button[contains(., '30일 무료 매칭 시작하기')]")
        log("Step 5", "'30일 무료 매칭 시작하기' 클릭", "PASS"); passed += 1

        # ---- 대시보드 로딩 대기 ----
        time.sleep(5)
        for _ in range(12):
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "기업 분석" in body_text or "정보 관리" in body_text:
                log("결과", "대시보드 로드 성공", "PASS"); passed += 1
                break
            time.sleep(5)
        else:
            body = driver.find_element(By.TAG_NAME, "body").text[:200]
            log("결과", f"대시보드 미도달: {body[:120]}", "FAIL"); failed += 1

        token = driver.execute_script("return localStorage.getItem('auth_token');")
        if token:
            log("인증", f"JWT 토큰 저장 확인 (길이: {len(token)})", "PASS"); passed += 1
        else:
            log("인증", "JWT 토큰이 저장되지 않음", "FAIL"); failed += 1

        print()

        # =============================================
        # Phase 2: 로그아웃
        # =============================================
        print("Phase 2: 로그아웃")
        print("-" * 40)

        try:
            logout_btn = driver.find_element(By.XPATH, "//button[contains(text(), '로그아웃')]")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", logout_btn)
            time.sleep(0.3)
            logout_btn.click()
            time.sleep(2)

            token_after = driver.execute_script("return localStorage.getItem('auth_token');")
            if not token_after:
                log("로그아웃", "토큰 제거 확인", "PASS"); passed += 1
            else:
                log("로그아웃", "토큰 남아있음", "FAIL"); failed += 1

            wait_for_text(driver, "다시 오셨군요", timeout=10)
            log("로그아웃", "로그인 화면 전환 확인", "PASS"); passed += 1
        except Exception as e:
            log("로그아웃", f"실패: {e}", "FAIL"); failed += 1

        print()

        # =============================================
        # Phase 3: 재로그인 (아이디+도메인 UI)
        # =============================================
        print("Phase 3: 재로그인")
        print("-" * 40)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='아이디']"))
            )
            fill_email(driver, TEST_EMAIL_ID, TEST_EMAIL_DOMAIN)
            log("로그인", f"이메일 입력: {TEST_EMAIL}", "PASS"); passed += 1

            pw_field = driver.find_element(By.XPATH, "//input[@type='password']")
            pw_field.clear()
            pw_field.send_keys(TEST_PASSWORD)
            log("로그인", "비밀번호 입력 완료", "PASS"); passed += 1

            login_btn = driver.find_element(By.XPATH, "//button[contains(., '로그인') and not(contains(., '로그아웃'))]")
            login_btn.click()
            log("로그인", "'로그인' 클릭", "PASS"); passed += 1

            time.sleep(5)
            for _ in range(12):
                body_text = driver.find_element(By.TAG_NAME, "body").text
                if "기업 분석" in body_text or "정보 관리" in body_text:
                    log("로그인", "대시보드 재진입 성공", "PASS"); passed += 1
                    break
                time.sleep(5)
            else:
                body_text = driver.find_element(By.TAG_NAME, "body").text[:150]
                log("로그인", f"대시보드 미도달: {body_text[:100]}", "FAIL"); failed += 1

            token_login = driver.execute_script("return localStorage.getItem('auth_token');")
            if token_login:
                log("로그인", f"JWT 토큰 발급 확인 (길이: {len(token_login)})", "PASS"); passed += 1
        except Exception as e:
            log("로그인", f"재로그인 실패: {e}", "FAIL"); failed += 1

        print()

        # =============================================
        # Phase 3.5: 결제 플로우 (베이직 업그레이드)
        # =============================================
        print("Phase 3.5: 결제 플로우 (업그레이드)")
        print("-" * 40)

        try:
            time.sleep(2)
            upgrade_btns = driver.find_elements(By.XPATH, "//button[contains(text(), '업그레이드')]")
            if not upgrade_btns:
                upgrade_btns = driver.find_elements(By.XPATH, "//button[contains(text(), '베이직 플랜 시작')]")

            if upgrade_btns:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", upgrade_btns[0])
                time.sleep(0.5)
                upgrade_btns[0].click()
                time.sleep(1)

                body_text = driver.find_element(By.TAG_NAME, "body").text
                if "베이직 플랜" in body_text and "2,900" in body_text:
                    log("결제모달", "PaymentModal 오픈 확인", "PASS"); passed += 1
                else:
                    log("결제모달", "PaymentModal 미확인", "FAIL"); failed += 1

                checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox']")
                if not checkbox.is_selected():
                    checkbox.click()
                    time.sleep(0.3)
                log("결제모달", "이용약관 동의 체크", "PASS"); passed += 1

                pay_btn = driver.find_element(By.XPATH, "//button[contains(., '2,900원으로 시작하기')]")
                pay_btn.click()
                log("결제모달", "'2,900원으로 시작하기' 클릭", "PASS"); passed += 1

                time.sleep(3)
                body_text = driver.find_element(By.TAG_NAME, "body").text
                if "베이직" in body_text:
                    log("결제", "플랜 업그레이드 확인 (베이직)", "PASS"); passed += 1

                    sidebar_btns = driver.find_elements(By.XPATH, "//button[contains(text(), '업그레이드')]")
                    if not sidebar_btns:
                        log("결제", "업그레이드 버튼 제거 확인 (basic 플랜)", "PASS"); passed += 1
                    else:
                        log("결제", "업그레이드 버튼 아직 표시됨", "FAIL"); failed += 1
                else:
                    log("결제", "플랜 변경 미확인", "FAIL"); failed += 1
            else:
                log("결제모달", "업그레이드 버튼 미발견", "FAIL"); failed += 1

        except Exception as e:
            log("결제", f"결제 테스트 실패: {str(e)[:80]}", "FAIL"); failed += 1

        print()

        # =============================================
        # Phase 4: 정보관리 확인
        # =============================================
        print("Phase 4: 정보관리 화면 확인")
        print("-" * 40)

        try:
            time.sleep(2)
            btns = driver.find_elements(By.XPATH, "//button[contains(., '정보 관리')]")
            if not btns:
                btns = driver.find_elements(By.XPATH, "//span[contains(text(), '정보 관리')]/ancestor::button")
            if not btns:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                btns = driver.find_elements(By.XPATH, "//button[contains(., '정보 관리')]")

            if btns:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btns[0])
                time.sleep(0.5)
                btns[0].click()
                time.sleep(2)

                body_text = driver.find_element(By.TAG_NAME, "body").text
                if "기업 정보 관리" in body_text or "소재지" in body_text:
                    log("정보관리", "정보관리 화면 도달", "PASS"); passed += 1

                    page_src = driver.page_source
                    for keyword, label in [("서울", "소재지"), ("1억 미만", "매출규모"), ("5인 미만", "직원수")]:
                        if keyword in page_src:
                            log("정보관리", f"{label} 프리필 확인", "PASS"); passed += 1
                        else:
                            log("정보관리", f"{label} 프리필 미확인", "FAIL"); failed += 1

                    close_btns = driver.find_elements(By.XPATH, "//button[contains(., '취소') or contains(., '닫기') or contains(., '돌아가기')]")
                    if close_btns:
                        close_btns[0].click()
                        time.sleep(1)
                        log("정보관리", "닫기 완료", "PASS"); passed += 1
                else:
                    log("정보관리", f"화면 전환 미확인", "FAIL"); failed += 1
            else:
                log("정보관리", "버튼 미발견", "FAIL"); failed += 1
        except Exception as e:
            log("정보관리", f"실패: {str(e)[:80]}", "FAIL"); failed += 1

        print()

        # =============================================
        # Phase 5: 이미 가입된 이메일로 온보딩 재시도
        # =============================================
        print("Phase 5: 409 처리 (이미 가입된 이메일)")
        print("-" * 40)

        try:
            clear_local_storage(driver)
            time.sleep(3)

            wait_for_text(driver, "기업 기본정보를 알려주세요", timeout=15)
            log("재온보딩", "온보딩 로드 확인", "PASS"); passed += 1

            wait_and_click(driver, "//button[contains(., '법인')]")
            time.sleep(0.5)
            set_react_input(driver, "input[type='date']", "2018-03-01")
            wait_and_click(driver, "//button[text()='경기']")
            time.sleep(0.3)

            driver.execute_script("""
                const inputs = document.querySelectorAll("input[type='date']");
                const textIn = document.querySelectorAll("input[placeholder='YYYY-MM-DD']");
                const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                if (inputs[0]) { setter.call(inputs[0], '2018-03-01'); inputs[0].dispatchEvent(new Event('change', {bubbles:true})); }
                if (textIn[0]) { setter.call(textIn[0], '2018-03-01'); textIn[0].dispatchEvent(new Event('change', {bubbles:true})); }
            """)
            time.sleep(0.3)

            wait_and_click(driver, "//button[contains(., '다음 단계로')]")
            time.sleep(1.5)

            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "관심 분야" not in body_text:
                wait_and_click(driver, "//button[contains(., '다음 단계로')]")
                time.sleep(1.5)

            interest_btns = driver.find_elements(
                By.XPATH, "//div[contains(@class,'grid')]//button[contains(@class,'rounded-2xl')]"
            )
            for btn in interest_btns[:2]:
                btn.click()
                time.sleep(0.2)
            wait_and_click(driver, "//button[contains(., '다음 단계로')]")
            time.sleep(1)

            wait_for_text(driver, "기업 규모를 알려주세요", timeout=10)
            wait_and_click(driver, "//button[contains(text(), '1억 ~ 5억')]")
            wait_and_click(driver, "//button[contains(text(), '5 ~ 10인')]")
            wait_and_click(driver, "//button[contains(., '다음 단계로')]")
            time.sleep(1)

            wait_for_text(driver, "업종을 선택해 주세요", timeout=10)
            wait_and_click(driver, "//button[contains(., '다음 단계로')]")
            time.sleep(1)

            # 같은 이메일 입력 (아이디 + 도메인)
            wait_for_text(driver, "맞춤 매칭 결과를 받아보세요", timeout=10)
            fill_email(driver, TEST_EMAIL_ID, TEST_EMAIL_DOMAIN)
            pw = driver.find_element(By.XPATH, "//input[@type='password']")
            pw.clear()
            pw.send_keys(TEST_PASSWORD)

            wait_and_click(driver, "//button[contains(., '30일 무료 매칭 시작하기')]")
            log("재온보딩", f"기존 이메일({TEST_EMAIL})로 등록 시도", "INFO")

            time.sleep(5)
            for _ in range(12):
                body = driver.find_element(By.TAG_NAME, "body").text
                if "기업 분석" in body or "정보 관리" in body:
                    log("재온보딩", "409 → 자동 로그인 → 대시보드 성공", "PASS"); passed += 1
                    break
                elif "다시 오셨군요" in body:
                    log("재온보딩", "409 → 로그인 화면 전환 (정상)", "PASS"); passed += 1
                    break
                time.sleep(5)
            else:
                body = driver.find_element(By.TAG_NAME, "body").text[:150]
                log("재온보딩", f"예상외: {body[:100]}", "FAIL"); failed += 1

        except Exception as e:
            log("재온보딩", f"실패: {e}", "FAIL"); failed += 1

        print()
        print(f"{'='*60}")
        print(f"  테스트 완료: {passed} PASSED / {failed} FAILED")
        print(f"{'='*60}")
        time.sleep(3)

    except Exception as e:
        print(f"\n  [FATAL] 치명적 오류: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()


if __name__ == "__main__":
    test_full_flow()
