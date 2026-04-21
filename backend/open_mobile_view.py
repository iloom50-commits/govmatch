#!/usr/bin/env python
"""스마트폰 크기 Chrome 창을 띄워 govmatch.kr 접속.

종료하지 않음 — 사장님이 직접 닫을 때까지 열려 있음.
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

URL = "https://govmatch.kr/"
# iPhone 14 Pro 크기 (모바일 기준)
DEVICE = {
    "deviceMetrics": {"width": 390, "height": 844, "pixelRatio": 3.0, "touch": True},
    "userAgent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
}

options = Options()
options.add_experimental_option("mobileEmulation", DEVICE)
options.add_experimental_option("detach", True)  # 스크립트 종료 후에도 창 유지
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--window-size=420,900")  # 실제 창 크기도 비슷하게

driver = webdriver.Chrome(options=options)
driver.get(URL)
print(f"[OK] {URL} 접속 완료. 창은 수동으로 닫아주세요.")
print(f"창 크기: 390x844 (iPhone 14 Pro)")
# 스크립트 종료 — detach=True라서 창은 열려 있음
