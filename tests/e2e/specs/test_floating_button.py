"""
모바일 플로팅 버튼 위치 테스트
- 비로그인 상태에서 '무료 가입' 버튼
- 로그인 상태에서 '내 정보' 버튼
- 버튼이 화면 좌측 하단(bottom-6 left-4)에 고정되는지 확인
- 페이지 로딩 중 중간 위치에 나타나지 않는지 확인
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

BASE_URL = "http://localhost:3000"

MOBILE_DEVICE = {
    "deviceMetrics": {"width": 390, "height": 844, "pixelRatio": 3.0},
    "userAgent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
}

def log(label, msg, ok=None):
    mark = "[PASS]" if ok is True else "[FAIL]" if ok is False else "[INFO]"
    print(f"  {mark} {label}: {msg}")


def create_mobile_driver():
    opts = Options()
    opts.add_experimental_option("mobileEmulation", MOBILE_DEVICE)
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(2)
    return driver


def get_button_info(driver, btn):
    """버튼의 실제 CSS position, 화면 위치, 표시 여부 반환"""
    info = driver.execute_script("""
        const btn = arguments[0];
        const rect = btn.getBoundingClientRect();
        const style = window.getComputedStyle(btn);
        return {
            position: style.position,
            display: style.display,
            visibility: style.visibility,
            opacity: style.opacity,
            bottom: rect.bottom,
            top: rect.top,
            left: rect.left,
            right: rect.right,
            width: rect.width,
            height: rect.height,
            viewportH: window.innerHeight,
            viewportW: window.innerWidth
        };
    """, btn)
    return info


def test_floating_button_position():
    print("\n=== 모바일 플로팅 버튼 위치 테스트 ===\n")
    driver = create_mobile_driver()
    results = []

    try:
        # ── 1. 페이지 로드 직후 즉시 스냅샷 (애니메이션 중 위치 확인)
        print("[1] 페이지 첫 로드 — 애니메이션 중 버튼 위치")
        driver.get(BASE_URL)
        time.sleep(0.5)  # 애니메이션 시작 직후 (700ms 이전)

        btns = driver.find_elements(By.XPATH, "//*[contains(text(),'무료 가입') or contains(text(),'내 정보')]")
        visible_during_anim = [b for b in btns if b.is_displayed()]

        if visible_during_anim:
            for b in visible_during_anim:
                info = get_button_info(driver, b)
                text = b.text.strip()
                pos = info["position"]
                top = info["top"]
                vh = info["viewportH"]
                # 버튼이 화면 중앙(vh의 20%~80%)에 있으면 버그
                in_center = (vh * 0.2) < top < (vh * 0.8)
                log(f"애니메이션 중 '{text}' position", f"{pos}, top={top:.0f}px (뷰포트 {vh}px)", ok=not in_center)
                results.append(not in_center)
                if in_center:
                    log(f"  -> 버그 감지", f"버튼이 화면 중앙({top:.0f}px)에 표시됨", ok=False)
        else:
            log("애니메이션 중", "버튼이 아직 DOM에 없거나 숨겨져 있음 (정상)", ok=True)
            results.append(True)

        # ── 2. 애니메이션 완료 후 버튼 위치
        print("\n[2] 애니메이션 완료 후 (1초 대기)")
        time.sleep(1.0)  # 700ms 애니메이션 완료 대기

        btns = driver.find_elements(By.XPATH, "//*[contains(text(),'무료 가입') or contains(text(),'내 정보')]")
        visible_after = [b for b in btns if b.is_displayed()]

        if visible_after:
            for b in visible_after:
                info = get_button_info(driver, b)
                text = b.text.strip()
                pos = info["position"]
                top = info["top"]
                left = info["left"]
                vh = info["viewportH"]
                vw = info["viewportW"]
                h = info["height"]

                # fixed 이어야 함
                is_fixed = pos == "fixed"
                # 좌측 하단: left ≈ 16px (left-4 = 1rem), bottom ≈ 24px (bottom-6 = 1.5rem)
                expected_left = 16
                expected_bottom_from_top = vh - 24 - h  # approx
                at_bottom_left = left < 40 and top > (vh * 0.7)

                log(f"'{text}' CSS position", pos, ok=is_fixed)
                log(f"'{text}' 화면 위치", f"top={top:.0f}px left={left:.0f}px (뷰포트 {vw}x{vh})", ok=at_bottom_left)
                results.extend([is_fixed, at_bottom_left])

                if not is_fixed:
                    log(f"  -> 버그", f"position이 fixed가 아님: {pos}", ok=False)
                if not at_bottom_left:
                    log(f"  -> 버그", f"버튼이 좌측 하단이 아님 (top={top:.0f}, left={left:.0f})", ok=False)
        else:
            log("애니메이션 후", "버튼을 찾을 수 없음 — lg 이상 화면이거나 조건 미충족", ok=None)

        # ── 3. 스크롤해도 위치 고정 확인
        print("\n[3] 스크롤 후 버튼 위치 고정 확인")
        driver.execute_script("window.scrollTo(0, 500)")
        time.sleep(0.5)

        btns = driver.find_elements(By.XPATH, "//*[contains(text(),'무료 가입') or contains(text(),'내 정보')]")
        visible_scroll = [b for b in btns if b.is_displayed()]

        if visible_scroll:
            for b in visible_scroll:
                info = get_button_info(driver, b)
                text = b.text.strip()
                top_after_scroll = info["top"]
                vh = info["viewportH"]
                at_bottom = top_after_scroll > (vh * 0.7)
                log(f"스크롤 후 '{text}' 위치", f"top={top_after_scroll:.0f}px", ok=at_bottom)
                results.append(at_bottom)

    finally:
        driver.quit()

    # ── 결과
    print(f"\n{'='*40}")
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    total = len(results)
    print(f"결과: {passed}/{total} 통과" + (f"  [{failed}개 실패]" if failed else "  [모두 통과]"))
    return failed == 0


if __name__ == "__main__":
    import sys
    ok = test_floating_button_position()
    sys.exit(0 if ok else 1)
