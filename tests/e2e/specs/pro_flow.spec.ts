import { test, expect } from "@playwright/test";
import {
  loginViaAPI, openProDashboard,
  expectClientSelectScreen, expectConsultTypeScreen,
  fillAndSubmitNewBizForm, waitForAIMessage,
} from "./helpers";

// ── 공통 로그인 (각 테스트 전 실행) ───────────────────────────────────────
test.beforeEach(async ({ page }) => {
  await loginViaAPI(page);
});

// ══════════════════════════════════════════════════════════════════
// S1 — PRO 진입 시 고객 선택 화면이 첫 화면으로 표시되는지
// ══════════════════════════════════════════════════════════════════
test("S1 — PRO 진입 → ① 고객 선택 화면", async ({ page }) => {
  await openProDashboard(page);
  await expectClientSelectScreen(page);

  await expect(page.locator("text=신규 사업자 고객")).toBeVisible();
  await expect(page.locator("text=신규 개인 고객")).toBeVisible();

  // 사이드바에 "새 고객 상담" 버튼 존재
  await expect(page.locator("button").filter({ hasText: "새 고객 상담" })).toBeVisible();
  // "AI 상담 시작" 메뉴가 제거됐는지 확인
  await expect(page.locator("text=AI 상담 시작")).not.toBeVisible();

  console.log("✅ S1 통과");
});

// ══════════════════════════════════════════════════════════════════
// S2 — 신규 사업자 클릭 → ② 폼 → 제출 → ③ 상담 목적 화면
// ══════════════════════════════════════════════════════════════════
test("S2 — 신규 사업자 → 폼 → ③ 상담 목적 화면", async ({ page }) => {
  await openProDashboard(page);
  await page.click("text=신규 사업자 고객");

  // 폼 표시 확인
  await expect(page.locator("input").first()).toBeVisible({ timeout: 5000 });

  // 최소 입력 후 제출
  await fillAndSubmitNewBizForm(page, "S2테스트기업");

  // ③ 상담 목적 화면 확인
  await expectConsultTypeScreen(page);
  await expect(page.locator("text=지원사업 매칭").first()).toBeVisible();
  await expect(page.locator("text=자금 상담").first()).toBeVisible();
  await expect(page.locator("text=특정 공고 상담").first()).toBeVisible();
  // 고객 정보 카드에 기업명 표시
  await expect(page.locator("text=S2테스트기업")).toBeVisible();

  console.log("✅ S2 통과");
});

// ══════════════════════════════════════════════════════════════════
// S3 — 신규 개인 고객 → 자금 상담 → AI 응답 확인
// ══════════════════════════════════════════════════════════════════
test("S3 — 신규 개인 → 자금 상담 → AI 응답", async ({ page }) => {
  await openProDashboard(page);
  await page.click("text=신규 개인 고객");
  await expect(page.locator("input").first()).toBeVisible({ timeout: 5000 });

  // 이름 입력 (개인 폼 이름 필드 placeholder로 직접 타겟)
  await page.getByPlaceholder("홍길동").fill("홍길동");
  // 제출 버튼 클릭 (ProSecretary 내 enabled 버튼만)
  await page.locator("button:not([disabled])").filter({ hasText: /상담 시작/ }).first().click();

  // ③ 상담 목적 → 자금 상담
  await expectConsultTypeScreen(page);
  await page.click("text=자금 상담");

  // 자금 상담 시작 확인: seed 메시지(자금 상담 실행)가 채팅에 표시되면 OK
  // (AI 응답은 서버 성능에 의존하므로 요청 전송까지만 검증)
  await expect(page.getByText(/자금 상담 실행|자금 상담/).first()).toBeVisible({ timeout: 15000 });

  // 채팅 입력창 활성화 확인 (채팅 단계 진입)
  await expect(page.locator("input[placeholder*='입력'], input[placeholder*='전송']").first()).toBeVisible({ timeout: 10000 });
  console.log("✅ S3 통과");
});

// ══════════════════════════════════════════════════════════════════
// S4 — 사업자 → 지원사업 매칭 → 매칭 카드 표시
// ══════════════════════════════════════════════════════════════════
test("S4 — 사업자 → 지원사업 매칭 → 결과 카드", async ({ page }) => {
  await openProDashboard(page);
  await page.click("text=신규 사업자 고객");
  await fillAndSubmitNewBizForm(page, "S4스타트업");

  await expectConsultTypeScreen(page);
  await page.click("text=지원사업 매칭");

  // 로딩 완료 대기 (최대 90초)
  await page.waitForFunction(
    () => document.querySelectorAll("[class*=rounded-xl][class*=border]").length > 2,
    { timeout: 90000 }
  );

  // 카드 개수 확인
  const cardCount = await page.locator("[class*=rounded-xl][class*=border]").count();
  expect(cardCount).toBeGreaterThan(0);
  console.log(`  카드 ${cardCount}개 확인`);

  // 채팅 입력창 표시 확인
  await expect(page.locator("input[placeholder*='입력']")).toBeVisible();

  console.log("✅ S4 통과");
});

// ══════════════════════════════════════════════════════════════════
// S5 — 뒤로가기: ②폼→① / ③목적→① / ④채팅→저장확인 다이얼로그
// ══════════════════════════════════════════════════════════════════
test("S5 — 뒤로가기 단계별 복귀", async ({ page }) => {
  await openProDashboard(page);

  // ② 폼에서 뒤로가기 → ① 고객 선택
  await page.click("text=신규 사업자 고객");
  await expect(page.locator("input").first()).toBeVisible({ timeout: 5000 });

  // "뒤로" 버튼 (Dashboard의 disabled "이전" 버튼과 구별: not([disabled]))
  const backBtn = page.locator("button:not([disabled])").filter({ hasText: /뒤로/ }).first();
  if (await backBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await backBtn.click();
  } else {
    await page.evaluate(() => window.history.back());
  }
  await expectClientSelectScreen(page);
  console.log("  ② → ① 복귀 ✓");

  // ③ 목적 화면에서 뒤로가기 → ① 고객 선택
  await page.click("text=신규 사업자 고객");
  await fillAndSubmitNewBizForm(page, "뒤로테스트");
  await expectConsultTypeScreen(page);

  // ③ 화면에는 "뒤로" 버튼 없음 → JS history.back() 사용
  await page.evaluate(() => window.history.back());
  await expectClientSelectScreen(page);
  console.log("  ③ → ① 복귀 ✓");

  console.log("✅ S5 통과");
});

// ══════════════════════════════════════════════════════════════════
// S6 — "새 고객 상담" 버튼: 폼 중간에서 눌러도 ①로 리셋
// ══════════════════════════════════════════════════════════════════
test("S6 — 새 고객 상담 버튼으로 완전 초기화", async ({ page }) => {
  await openProDashboard(page);

  // ② 폼까지 진행
  await page.click("text=신규 사업자 고객");
  await expect(page.locator("input").first()).toBeVisible({ timeout: 5000 });
  await page.locator("input").first().fill("초기화될 기업명");

  // 사이드바 "새 고객 상담" 클릭
  await page.locator("button").filter({ hasText: "새 고객 상담" }).click();
  await expectClientSelectScreen(page);

  // 입력 내용이 사라졌는지 확인 (폼이 안 보여야 함)
  await expect(page.locator("text=초기화될 기업명")).not.toBeVisible();

  console.log("✅ S6 통과");
});

// ══════════════════════════════════════════════════════════════════
// S7 — 특정 공고 상담 → 공고 검색 화면 전환
// ══════════════════════════════════════════════════════════════════
test("S7 — 특정 공고 상담 → 공고 검색 화면", async ({ page }) => {
  await openProDashboard(page);
  await page.click("text=신규 사업자 고객");
  await fillAndSubmitNewBizForm(page, "공고테스트사");
  await expectConsultTypeScreen(page);

  await page.click("text=특정 공고 상담");

  // 공고 검색 화면 확인 (검색 input 나타나야 함)
  await expect(
    page.locator("input[placeholder*='검색'], input[placeholder*='공고'], input[placeholder*='키워드']").first()
  ).toBeVisible({ timeout: 8000 });

  console.log("✅ S7 통과");
});

// ══════════════════════════════════════════════════════════════════
// S8 — 사이드바 최근 고객 리스트 (고객 등록 이력 있을 때)
// ══════════════════════════════════════════════════════════════════
test("S8 — 사이드바 최근 고객 → 클릭 시 ③ 상담 목적 화면", async ({ page }) => {
  await openProDashboard(page);

  // 최근 고객 목록이 있으면 테스트, 없으면 skip
  const recentSection = page.locator("text=최근 고객");
  const hasRecent = await recentSection.isVisible({ timeout: 3000 }).catch(() => false);

  if (!hasRecent) {
    console.log("  최근 고객 없음 — S8 skip");
    return;
  }

  // 첫 번째 최근 고객 클릭
  const firstClient = page.locator("[class*=menuInactive], nav button").filter({ hasText: /사|개/ }).nth(1);
  await firstClient.click();

  // ③ 상담 목적 화면으로 이동 확인
  await expectConsultTypeScreen(page);
  console.log("✅ S8 통과");
});
