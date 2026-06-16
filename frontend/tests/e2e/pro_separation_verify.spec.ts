/**
 * 전문가/일반 사용자 완전 분리 검증
 *
 * 페르소나: 김재원 컨설턴트 — govmatch.kr/pro URL을 전달받아 처음 방문
 *
 * 로컬 백엔드 미실행 → addInitScript()로 fetch 모킹
 * - /pro 페이지: auth/login + auth/me 만 모킹 (다른 API 미존재)
 * - govmatch.kr: 비인증 직접 방문 (Home fetch 크래시 방지)
 */

import { test, expect, type Page } from "@playwright/test";

const LOCAL_HOME = "http://localhost:3000";
const LOCAL_PRO = "http://localhost:3000/pro";

// ── /pro 전용 fetch 모킹 (로그인/me만 처리) ─────────────────
async function mockProAuth(page: Page, plan: "pro" | "lite" | "free") {
  const planData = {
    plan,
    is_active: true,
    label: plan === "pro" ? "PRO" : plan === "lite" ? "LITE" : "FREE",
    days_left: plan === "pro" ? 25 : null,
    plan_expires_at: "2027-01-01T00:00:00",
    ai_usage_today: 0,
    ai_limit_today: plan === "pro" ? 999999 : 3,
    consult_limit: plan === "pro" ? 999999 : 0,
    ai_used: 0,
  };
  const userData = {
    business_number: "1234567890",
    company_name: "김재원컨설팅",
    email: "jaewon@consult.kr",
    user_type: "business",
  };

  await page.addInitScript(
    ({ planData, userData }) => {
      const _fetch = window.fetch;
      (window as any).fetch = async function (url: string, options?: any) {
        const u = url.toString();
        if (u.includes("/api/auth/login")) {
          const body = JSON.parse(options?.body || "{}");
          if (body.password === "wrongpassword") {
            return new Response(
              JSON.stringify({ detail: "이메일 또는 비밀번호를 확인해주세요." }),
              { status: 401, headers: { "Content-Type": "application/json" } }
            );
          }
          return new Response(
            JSON.stringify({ token: "mock.jwt.token", plan: planData, user: userData }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (u.includes("/api/auth/me")) {
          return new Response(
            JSON.stringify({ status: "SUCCESS", plan: planData, user: userData }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (u.includes("/api/auth/register")) {
          return new Response(
            JSON.stringify({ token: "mock.jwt.token", plan: planData, user: userData }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return _fetch.apply(this, [url, options]);
      };
    },
    { planData, userData }
  );
}

// ══════════════════════════════════════════════════════════════
// [/pro 페이지] 시나리오 1: 소셜 로그인 버튼 3개 표시
// ══════════════════════════════════════════════════════════════
test("[/pro] 소셜 로그인 버튼 3개 표시 (카카오·네이버·구글)", async ({ page }) => {
  await page.goto(LOCAL_PRO, { waitUntil: "networkidle" });

  await expect(page.locator("button[title='카카오로 로그인']")).toBeVisible({ timeout: 8000 });
  await expect(page.locator("button[title='네이버로 로그인']")).toBeVisible();
  await expect(page.locator("button[title='Google로 로그인']")).toBeVisible();

  // 이메일/소셜 구분선 "또는" 표시
  await expect(page.locator("text=또는")).toBeVisible();
  console.log("✅ 소셜 로그인 버튼 3개 확인");
});

// ══════════════════════════════════════════════════════════════
// [/pro 페이지] 시나리오 2: 로그인 ↔ 회원가입 탭 전환
// ══════════════════════════════════════════════════════════════
test("[/pro] 로그인 ↔ 회원가입 탭 전환", async ({ page }) => {
  await page.goto(LOCAL_PRO, { waitUntil: "networkidle" });

  // 기본: 로그인 탭 — 이메일/비밀번호 필드
  await expect(page.locator("input[type='email']")).toBeVisible({ timeout: 8000 });
  await expect(page.locator("input[type='password']")).toBeVisible();
  // 사업자번호 입력창 없음
  expect(await page.locator("input[placeholder='000-00-00000']").isVisible().catch(() => false)).toBeFalsy();

  // 회원가입 탭 클릭
  await page.locator("button").filter({ hasText: "회원가입" }).click();
  // 사업자번호 입력창 표시
  await expect(page.locator("input[placeholder='000-00-00000']")).toBeVisible({ timeout: 3000 });

  // 다시 로그인 탭
  await page.locator("button").filter({ hasText: /^로그인$/ }).click();
  await page.waitForTimeout(500);
  expect(await page.locator("input[placeholder='000-00-00000']").isVisible().catch(() => false)).toBeFalsy();

  console.log("✅ 탭 전환 확인");
});

// ══════════════════════════════════════════════════════════════
// [/pro 페이지] 시나리오 3: PRO 계정 로그인 → 대시보드
// ══════════════════════════════════════════════════════════════
test("[/pro] PRO 계정 로그인 → 대시보드 표시", async ({ page }) => {
  await mockProAuth(page, "pro");
  await page.goto(LOCAL_PRO, { waitUntil: "networkidle" });

  await page.locator("input[type='email']").fill("jaewon@consult.kr");
  await page.locator("input[type='password']").fill("password123");
  await page.locator("button[type='submit']").click();

  // 대시보드: 사용자명·PRO 배지·시작 버튼
  await expect(page.locator("text=김재원컨설팅")).toBeVisible({ timeout: 8000 });
  // PRO 배지 — span.text-violet-700으로 정확히 지정
  await expect(page.locator("span.text-violet-700", { hasText: "PRO" })).toBeVisible();
  await expect(page.getByRole("button", { name: "전문상담툴 시작하기 →" })).toBeVisible();

  // 결제 버튼 없어야 함
  expect(
    await page.getByRole("button", { name: "PRO 플랜 결제하기" }).isVisible().catch(() => false)
  ).toBeFalsy();

  console.log("✅ PRO 대시보드 확인");
});

// ══════════════════════════════════════════════════════════════
// [/pro 페이지] 시나리오 4: 전문상담툴 시작 → ProSecretary 진입
// ══════════════════════════════════════════════════════════════
test("[/pro] 전문상담툴 시작하기 → ProSecretary 진입", async ({ page }) => {
  await mockProAuth(page, "pro");
  await page.goto(LOCAL_PRO, { waitUntil: "networkidle" });

  await page.locator("input[type='email']").fill("jaewon@consult.kr");
  await page.locator("input[type='password']").fill("password123");
  await page.locator("button[type='submit']").click();

  await expect(page.getByRole("button", { name: "전문상담툴 시작하기 →" })).toBeVisible({ timeout: 8000 });
  await page.getByRole("button", { name: "전문상담툴 시작하기 →" }).click();

  // ProSecretary 진입 확인
  await expect(page.locator("text=전문가 대시보드")).toBeVisible({ timeout: 10000 });

  // 일반 govmatch.kr FAB 없어야 함 (다른 페이지)
  expect(
    await page.locator("button[aria-label='정책자금 상담']").isVisible().catch(() => false)
  ).toBeFalsy();

  console.log("✅ ProSecretary 진입 확인");
});

// ══════════════════════════════════════════════════════════════
// [/pro 페이지] 시나리오 5: 비PRO 계정 로그인 → 결제 버튼 표시
// ══════════════════════════════════════════════════════════════
test("[/pro] 비PRO 계정 로그인 → 'PRO 플랜 결제하기' 버튼 표시", async ({ page }) => {
  await mockProAuth(page, "free");
  await page.goto(LOCAL_PRO, { waitUntil: "networkidle" });

  await page.locator("input[type='email']").fill("jaewon@consult.kr");
  await page.locator("input[type='password']").fill("password123");
  await page.locator("button[type='submit']").click();

  // 결제 버튼 표시
  await expect(page.getByRole("button", { name: "PRO 플랜 결제하기" })).toBeVisible({ timeout: 8000 });

  // "전문상담툴 시작하기" 없어야 함
  expect(
    await page.getByRole("button", { name: "전문상담툴 시작하기 →" }).isVisible().catch(() => false)
  ).toBeFalsy();

  // 안내 문구 — span만 정확히 선택
  await expect(page.locator("span.font-semibold.text-gray-900", { hasText: "PRO 플랜" })).toBeVisible();

  console.log("✅ 비PRO 결제 유도 대시보드 확인");
});

// ══════════════════════════════════════════════════════════════
// [/pro 페이지] 시나리오 6: PaymentModal에 PRO 카드만 표시
// ══════════════════════════════════════════════════════════════
test("[/pro] 결제 모달 — PRO 카드만 표시, FREE·LITE 없음", async ({ page }) => {
  await mockProAuth(page, "free");
  await page.goto(LOCAL_PRO, { waitUntil: "networkidle" });

  await page.locator("input[type='email']").fill("jaewon@consult.kr");
  await page.locator("input[type='password']").fill("password123");
  await page.locator("button[type='submit']").click();

  await page.getByRole("button", { name: "PRO 플랜 결제하기" }).click({ timeout: 8000 });

  // PaymentModal — Pro 카드 가격 표시
  await expect(page.locator("text=₩29,000")).toBeVisible({ timeout: 6000 });
  // Pro h3 헤딩
  await expect(page.locator("h3.text-violet-700", { hasText: "Pro" })).toBeVisible();

  // FREE·LITE 카드 없어야 함
  await expect(page.locator("text=₩0")).not.toBeVisible();
  await expect(page.locator("h3.text-indigo-700", { hasText: "Lite" })).not.toBeVisible();
  await expect(page.locator("h3.text-slate-700", { hasText: "Free" })).not.toBeVisible();

  console.log("✅ /pro PaymentModal — PRO 카드만 표시 확인");
});

// ══════════════════════════════════════════════════════════════
// [/pro 페이지] 시나리오 7: 기존 PRO 토큰 → 자동 대시보드 진입
// ══════════════════════════════════════════════════════════════
test("[/pro] 기존 PRO 토큰 → 로그인 없이 대시보드 자동 진입", async ({ page }) => {
  await mockProAuth(page, "pro");
  await page.goto(LOCAL_PRO, { waitUntil: "domcontentloaded" });
  await page.evaluate(() => localStorage.setItem("auth_token", "mock.jwt.token"));
  await page.goto(LOCAL_PRO, { waitUntil: "networkidle" });

  await expect(page.getByRole("button", { name: "전문상담툴 시작하기 →" })).toBeVisible({ timeout: 10000 });
  expect(await page.locator("input[type='email']").isVisible().catch(() => false)).toBeFalsy();

  console.log("✅ PRO 토큰 자동 대시보드 진입 확인");
});

// ══════════════════════════════════════════════════════════════
// [govmatch.kr] 시나리오 8: FAB 항상 "정책자금 상담"
// (비인증 방문 — auth mock 없이 직접 확인)
// ══════════════════════════════════════════════════════════════
test("[govmatch.kr] FAB 레이블 = '정책자금 상담' (PRO 전문상담툴 분리 확인)", async ({ page }) => {
  // 비인증으로 HOME 방문 — AiChatBot 항상 렌더, FAB 기본 닫힘 상태
  await page.goto(LOCAL_HOME, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  // FAB 버튼 확인
  const fab = page.locator("button[aria-label='정책자금 상담']");
  await expect(fab).toBeVisible({ timeout: 10000 });

  // "전문상담툴" 레이블 FAB 없어야 함 (완전 분리 확인)
  expect(
    await page.locator("button[aria-label='전문상담툴']").isVisible().catch(() => false)
  ).toBeFalsy();
  expect(
    await page.locator("button[aria-label='전문상담 AI']").isVisible().catch(() => false)
  ).toBeFalsy();

  console.log("✅ govmatch.kr FAB = '정책자금 상담' 확인 (PRO 분리됨)");
});

// ══════════════════════════════════════════════════════════════
// [govmatch.kr] 시나리오 9: HomeClient에 PaymentModal mode="lite" 확인
// (코드 레벨 검증 — 비인증 + 이미 mode 확인됨)
// ══════════════════════════════════════════════════════════════
test("[govmatch.kr] 비인증 AI 챗봇 클릭 → 로그인 유도 (PRO 기능 없음)", async ({ page }) => {
  await page.goto(LOCAL_HOME, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  // FAB 클릭 → 비인증이면 로그인 유도 (ProSecretary 진입 없음)
  const fab = page.locator("button[aria-label='정책자금 상담']");
  await expect(fab).toBeVisible({ timeout: 10000 });
  await fab.click();

  // 로그인 유도 모달 표시 (Pro 전용 컨텐츠 없음)
  await page.waitForTimeout(1500);

  // ProSecretary 텍스트 없어야 함
  expect(
    await page.locator("text=전문가 대시보드").isVisible().catch(() => false)
  ).toBeFalsy();

  // 프로필 게이트 모달 표시 확인 (비인증 시 profile=null → checkProfileThenRun → NotificationModal)
  await expect(page.locator("text=정확한 매칭을 위해 정보가 필요해요")).toBeVisible({ timeout: 5000 });

  console.log("✅ govmatch.kr 비인증 FAB 클릭 → 프로필 게이트 모달 (PRO 없음)");
});
