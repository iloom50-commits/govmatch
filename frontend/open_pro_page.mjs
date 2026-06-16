/**
 * /pro 페이지를 PRO 계정 로그인 상태로 열어두는 스크립트
 * 실행: node open_pro_page.mjs
 */
import { chromium } from '@playwright/test';

const planData = {
  plan: "pro", is_active: true, label: "PRO",
  days_left: 25, plan_expires_at: "2027-01-01T00:00:00",
  ai_usage_today: 0, ai_limit_today: 999999,
  consult_limit: 999999, ai_used: 0,
};
const userData = {
  business_number: "1234567890",
  company_name: "김재원컨설팅",
  email: "jaewon@consult.kr",
  user_type: "business",
};

const browser = await chromium.launch({ headless: false, slowMo: 0, args: ['--start-maximized'] });
const ctx = await browser.newContext({ viewport: null });
const page = await ctx.newPage();

// fetch mock
await page.addInitScript(({ planData, userData }) => {
  const _fetch = window.fetch;
  window.fetch = async function(url, opts) {
    const u = url.toString();
    if (u.includes("/api/auth/me")) {
      return new Response(
        JSON.stringify({ status: "SUCCESS", plan: planData, user: userData }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    if (u.includes("/api/auth/login")) {
      return new Response(
        JSON.stringify({ token: "mock.jwt.token", plan: planData, user: userData }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    return _fetch.apply(this, [url, opts]);
  };
}, { planData, userData });

// localStorage에 토큰 주입
await page.goto("http://localhost:3000/pro", { waitUntil: "domcontentloaded" });
await page.evaluate(() => localStorage.setItem("auth_token", "mock.jwt.token"));
await page.reload({ waitUntil: "networkidle" });

console.log("✅ /pro 페이지 열림 — PRO 계정 로그인 상태");
console.log("   확인 후 브라우저를 닫으면 종료됩니다.");

// 브라우저 닫힐 때까지 대기
await page.waitForEvent("close", { timeout: 300000 }).catch(() => {});
await browser.close();
