/**
 * 모바일 무한스크롤 페이지네이션 — 누적 동작 검증
 *
 * fix(dashboard): 모바일에서 스크롤 시 공고가 교체되지 않고 누적되어야 함
 *   - 일반 탭: 스크롤 → 2페이지 공고가 1페이지에 누적 추가
 *   - 맞춤 모드: 스크롤 → 2페이지 맞춤 공고가 1페이지에 누적 추가 (버그 수정 검증)
 */

import { test, expect } from '@playwright/test';

const SITE = 'https://www.govmatch.kr';
const API  = 'https://govmatch-production.up.railway.app';

// iPhone 14 Pro 해상도 (모바일 무한스크롤 분기 기준: width < 768)
const MOBILE_VIEWPORT = { width: 390, height: 844 };

test.setTimeout(180_000);

// ── 완성 프로필 고정 테스트 계정 ──────────────────────────────────────
const COMPLETE_EMAIL    = 'test_complete_pagination@test-govmatch.com';
const COMPLETE_PASSWORD = 'Test1234!';
let completeToken = '';

/** 완성 프로필 계정 로그인 or 생성 + 프로필 완성 */
async function getOrCreateCompleteToken(request: any): Promise<string> {
  // 1) 로그인 먼저 시도
  const loginRes = await request.post(`${API}/api/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { email: COMPLETE_EMAIL, password: COMPLETE_PASSWORD },
  });
  const loginData = await loginRes.json();
  if (loginData.token) {
    console.log(`  → 완성 프로필 계정 로그인 성공: ${COMPLETE_EMAIL}`);
    return loginData.token;
  }

  // 2) 없으면 가입
  console.log(`  → 완성 프로필 계정 미존재, 신규 가입...`);
  const regRes = await request.post(`${API}/api/auth/register`, {
    headers: { 'Content-Type': 'application/json' },
    data: {
      email:           COMPLETE_EMAIL,
      password:        COMPLETE_PASSWORD,
      business_number: 'T888888888',
      company_name:    '페이지네이션테스트',
    },
  });
  const regData = await regRes.json();
  if (!regData.token) throw new Error(`계정 생성 실패: ${JSON.stringify(regData)}`);

  const token = regData.token;

  // 3) 프로필 완성 (isPublic = false 조건: address_city or interests 중 하나라도 있으면 됨)
  await request.put(`${API}/api/profile`, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    data: {
      address_city: '서울',
      interests:    '창업지원,자금·지원,기술·개발',
      user_type:    'business',
    },
  });
  console.log(`  → 완성 프로필 계정 생성+프로필 완성: ${COMPLETE_EMAIL}`);
  return token;
}

/** 스켈레톤 사라지고 공고 카드 1개 이상 보일 때까지 대기 */
async function waitForCards(page: any, timeout = 45_000): Promise<void> {
  // networkidle로 auth + 공고 API 완료 대기
  await page.waitForLoadState('networkidle', { timeout }).catch(() => {});
  await page.waitForFunction(() => {
    const noSkeleton = !document.querySelector('.grid > div.animate-pulse');
    const cards = document.querySelectorAll('.grid > div:not(.animate-pulse)');
    return noSkeleton && cards.length > 0;
  }, { timeout });
}

/** 현재 화면에 표시된 공고 카드 수 반환 */
async function countCards(page: any): Promise<number> {
  return page.evaluate(() => {
    // ResultCard는 grid 안의 div (스켈레톤 제외)
    return document.querySelectorAll('.grid > div:not(.animate-pulse)').length;
  });
}

/** sentinel이 뷰포트에 들어올 때까지 천천히 스크롤 */
async function scrollToSentinel(page: any): Promise<void> {
  // sentinel은 h-2 div이고 list 맨 아래 위치
  // 페이지 끝까지 천천히 스크롤해서 200px rootMargin 안에 들어오게
  await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
  await page.waitForTimeout(1_500);
}

// ── beforeAll: 토큰 준비 ──────────────────────────────────────────────

test.beforeAll(async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: MOBILE_VIEWPORT });
  completeToken = await getOrCreateCompleteToken(ctx.request);
  await ctx.close();
});

// ═══════════════════════════════════════════════════════════════════════
// 테스트 1: 일반 탭 모바일 무한스크롤 — 2페이지 누적 확인
// ═══════════════════════════════════════════════════════════════════════
test('일반 탭: 모바일 스크롤 시 1페이지 공고가 사라지지 않고 2페이지가 누적된다', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: MOBILE_VIEWPORT, isMobile: true });
  const page = await ctx.newPage();

  await page.goto(SITE);
  await waitForCards(page);

  const page1Count = await countCards(page);
  console.log(`  → 1페이지 공고 수: ${page1Count}건`);
  expect(page1Count).toBeGreaterThan(0);

  // 스크롤해서 sentinel 노출 → 2페이지 로드 트리거
  await scrollToSentinel(page);

  // 2페이지 로드 대기 (스피너 사라질 때까지)
  await page.waitForFunction(
    () => !document.querySelector('.animate-spin'),
    { timeout: 20_000 }
  ).catch(() => {}); // 스피너가 없을 수도 있음
  await page.waitForTimeout(2_000);

  const afterScrollCount = await countCards(page);
  console.log(`  → 스크롤 후 공고 수: ${afterScrollCount}건`);

  // 핵심 검증: 공고가 교체됐다면 page1Count와 같음, 누적됐다면 더 많음
  expect(afterScrollCount).toBeGreaterThan(page1Count);
  console.log(`  ✅ 누적 확인: ${page1Count}건 → ${afterScrollCount}건 (${afterScrollCount - page1Count}건 추가)`);

  await ctx.close();
});

// ═══════════════════════════════════════════════════════════════════════
// 테스트 2: 맞춤 모드 모바일 무한스크롤 — 2페이지 누적 확인 (버그 수정 핵심)
// ═══════════════════════════════════════════════════════════════════════
test('맞춤 모드: 모바일 스크롤 시 1페이지 맞춤 공고가 사라지지 않고 2페이지가 누적된다', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: MOBILE_VIEWPORT, isMobile: true });
  const page = await ctx.newPage();

  // 완성 프로필 계정으로 로그인
  await page.goto(SITE);
  await page.evaluate((t) => localStorage.setItem('auth_token', t), completeToken);
  await page.reload();
  await waitForCards(page, 30_000);
  console.log('  → 완성 프로필 계정 로그인 완료');

  // nudge 팝업 닫기 (있을 경우)
  const dismissBtn = page.locator('button:has-text("나중에 할게요")');
  if (await dismissBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await dismissBtn.click();
    await page.waitForTimeout(300);
  }

  // ⭐맞춤 칩 클릭
  const matchedChip = page.locator('button').filter({ hasText: /⭐/ }).first();
  await matchedChip.waitFor({ timeout: 10_000 });
  await matchedChip.click();
  console.log('  → ⭐맞춤 칩 클릭');

  // 맞춤 공고 로드 대기 — amber 스켈레톤 사라질 때까지 (최대 60s, Railway 응답 대기)
  await page.waitForFunction(
    () => {
      const amberSkeleton = document.querySelector('.bg-amber-50.animate-pulse');
      const spinners = document.querySelector('.animate-spin');
      return !amberSkeleton && !spinners;
    },
    { timeout: 60_000 }
  ).catch(() => {});
  await page.waitForTimeout(1_500);

  const matchedPage1Count = await countCards(page);
  console.log(`  → 맞춤 1페이지 공고 수: ${matchedPage1Count}건`);

  // 맞춤 공고가 20건 미만이면 2페이지가 없으므로 테스트 스킵
  if (matchedPage1Count < 20) {
    console.log(`  ⚠️  맞춤 공고 ${matchedPage1Count}건 — 20건 미만이라 2페이지 없음, 스킵`);
    test.skip();
    await ctx.close();
    return;
  }

  // 스크롤해서 sentinel 노출
  await scrollToSentinel(page);
  await page.waitForFunction(
    () => !document.querySelector('.animate-spin'),
    { timeout: 30_000 }
  ).catch(() => {});
  await page.waitForTimeout(2_000);

  const afterScrollCount = await countCards(page);
  console.log(`  → 스크롤 후 맞춤 공고 수: ${afterScrollCount}건`);

  // 핵심 검증: 수정 전이면 afterScrollCount === 20 (교체), 수정 후면 > 20 (누적)
  expect(afterScrollCount).toBeGreaterThan(matchedPage1Count);
  console.log(`  ✅ 맞춤 누적 확인: ${matchedPage1Count}건 → ${afterScrollCount}건 (${afterScrollCount - matchedPage1Count}건 추가)`);

  await ctx.close();
});

// ═══════════════════════════════════════════════════════════════════════
// 테스트 3: 탭 전환 후 맞춤 모드 → 공고 초기화 확인 (회귀 방지)
// ═══════════════════════════════════════════════════════════════════════
test('탭 전환 시 맞춤 모드 공고가 초기화되고 새 탭 결과가 표시된다', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: MOBILE_VIEWPORT, isMobile: true });
  const page = await ctx.newPage();

  await page.goto(SITE);
  await page.evaluate((t) => localStorage.setItem('auth_token', t), completeToken);
  await page.reload();
  await waitForCards(page, 30_000);

  // nudge 팝업 닫기
  const dismissBtn = page.locator('button:has-text("나중에 할게요")');
  if (await dismissBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await dismissBtn.click();
    await page.waitForTimeout(300);
  }

  // 기업 지원금 탭에서 맞춤 모드 활성화
  const bizTab = page.locator('button:has-text("기업 지원금")').first();
  await bizTab.click();
  await waitForCards(page, 15_000);

  const matchedChip = page.locator('button').filter({ hasText: /⭐/ }).first();
  await matchedChip.click();
  await page.waitForTimeout(2_000);

  const bizMatchedCount = await countCards(page);
  console.log(`  → 기업 맞춤 공고: ${bizMatchedCount}건`);

  // 개인 지원금 탭으로 전환 → 맞춤 모드 자동 해제 + 공고 초기화
  const indTab = page.locator('button:has-text("개인 지원금")').first();
  await indTab.click();
  await waitForCards(page, 15_000);
  await page.waitForTimeout(1_000);

  // 탭 전환 후 맞춤 패널이 닫혔는지 확인 (맞춤 모드 자동 해제)
  const amberPanel = page.locator('button', { hasText: /^맞춤 설정하기$/ });
  const isAmberVisible = await amberPanel.isVisible({ timeout: 1_000 }).catch(() => false);
  expect(isAmberVisible).toBe(false);
  console.log('  ✅ 탭 전환 시 맞춤 모드 자동 해제 확인');

  // 공고가 새로 로드됐는지 확인 (0건이 아님)
  const indCount = await countCards(page);
  expect(indCount).toBeGreaterThan(0);
  console.log(`  ✅ 개인 탭 공고 로드 확인: ${indCount}건`);

  await ctx.close();
});
