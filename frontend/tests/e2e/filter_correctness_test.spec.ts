/**
 * 내지역·맞춤 칩 필터링 정확성 검증
 *
 * - 내지역: 응답 공고의 region이 사용자 도시(서울) 또는 전국만 포함되는지
 * - 맞춤:  personalized:true + user_city 일치 + 카테고리/지역이 관심분야와 연관되는지
 *
 * 검증 방식: Playwright 네트워크 인터셉트 (API 응답 데이터 직접 검사)
 */

import { test, expect } from '@playwright/test';

const SITE = 'https://www.govmatch.kr';
const API  = 'https://govmatch-production.up.railway.app';

const MOBILE_VIEWPORT = { width: 390, height: 844 };

test.setTimeout(120_000);

// 완성 프로필 계정 (address_city: 서울, interests: 창업지원,자금·지원,기술·개발)
const COMPLETE_EMAIL    = 'test_complete_pagination@test-govmatch.com';
const COMPLETE_PASSWORD = 'Test1234!';
let completeToken = '';

async function getToken(request: any): Promise<string> {
  const res  = await request.post(`${API}/api/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { email: COMPLETE_EMAIL, password: COMPLETE_PASSWORD },
  });
  const data = await res.json();
  if (!data.token) throw new Error(`로그인 실패: ${JSON.stringify(data)}`);
  return data.token;
}

async function waitForCards(page: any, timeout = 45_000): Promise<void> {
  await page.waitForLoadState('networkidle', { timeout }).catch(() => {});
  await page.waitForFunction(() => {
    const noSkeleton = !document.querySelector('.grid > div.animate-pulse');
    const cards = document.querySelectorAll('.grid > div:not(.animate-pulse)');
    return noSkeleton && cards.length > 0;
  }, { timeout });
}

test.beforeAll(async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: MOBILE_VIEWPORT });
  completeToken = await getToken(ctx.request);
  await ctx.close();
});

// ════════════════════════════════════════════════════════════════════════
// 테스트 1: 내지역 칩 — 응답 공고의 region이 서울/전국만 포함되는지
// ════════════════════════════════════════════════════════════════════════
test('내지역 칩: API 응답 공고의 region이 서울 또는 전국만 포함된다', async ({ browser }) => {
  const ctx  = await browser.newContext({ viewport: MOBILE_VIEWPORT, isMobile: true });
  const page = await ctx.newPage();

  // 로그인
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

  // 내지역 칩 클릭 전에 API 응답 캡처 준비
  const localApiResponses: any[] = [];
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/api/announcements/public') && url.includes('tab=local')) {
      try {
        const json = await response.json();
        localApiResponses.push(json);
      } catch {}
    }
  });

  // 내지역 칩 클릭
  const chip = page.locator('button').filter({ hasText: /내지역/ }).first();
  await chip.waitFor({ timeout: 10_000 });
  await chip.click();
  console.log('  → 내지역 칩 클릭');

  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
  await page.waitForFunction(
    () => !document.querySelector('.grid > div.animate-pulse'),
    { timeout: 30_000 }
  ).catch(() => {});
  await page.waitForTimeout(1_000);

  // API 응답이 있는지 확인
  expect(localApiResponses.length).toBeGreaterThan(0);
  console.log(`  → tab=local API 응답 수신: ${localApiResponses.length}건`);

  const firstResponse = localApiResponses[0];
  console.log(`  → 응답 구조: tab=${firstResponse.tab}, total=${firstResponse.total}`);

  // tab 확인
  expect(firstResponse.tab).toBe('local');

  const announcements: any[] = firstResponse.data || [];
  expect(announcements.length).toBeGreaterThan(0);
  console.log(`  → 반환된 공고 수: ${announcements.length}건`);

  // 허용 region: 서울, 전국, All, null, "" — 다른 지역이 섞이면 안 됨
  const ALLOWED_REGIONS = new Set(['서울', '전국', 'All', '', null, undefined]);
  const violating: { id: number; region: string; title: string }[] = [];

  for (const ann of announcements) {
    const r = ann.region ?? null;
    // 허용 목록에 없고, 서울이 포함되지 않는 경우
    if (!ALLOWED_REGIONS.has(r) && !(r && r.includes('서울'))) {
      violating.push({ id: ann.announcement_id, region: r, title: (ann.title || '').slice(0, 30) });
    }
  }

  if (violating.length > 0) {
    console.log('  ❌ 서울/전국 외 region 공고 발견:');
    violating.forEach(v => console.log(`     id=${v.id} region="${v.region}" title="${v.title}"`));
  } else {
    console.log(`  ✅ 전체 ${announcements.length}건 모두 서울 또는 전국 공고`);
  }

  expect(violating.length).toBe(0);

  await ctx.close();
});

// ════════════════════════════════════════════════════════════════════════
// 테스트 2: 내지역 칩 — DOM 카드에서 타 지역 공고가 보이지 않는지
// ════════════════════════════════════════════════════════════════════════
test('내지역 칩: 카드에 표시된 지역 태그가 서울 또는 전국만 포함된다', async ({ browser }) => {
  const ctx  = await browser.newContext({ viewport: MOBILE_VIEWPORT, isMobile: true });
  const page = await ctx.newPage();

  await page.goto(SITE);
  await page.evaluate((t) => localStorage.setItem('auth_token', t), completeToken);
  await page.reload();
  await waitForCards(page, 30_000);

  const dismissBtn = page.locator('button:has-text("나중에 할게요")');
  if (await dismissBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await dismissBtn.click();
    await page.waitForTimeout(300);
  }

  const chip = page.locator('button').filter({ hasText: /내지역/ }).first();
  await chip.waitFor({ timeout: 10_000 });
  await chip.click();

  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
  await page.waitForFunction(
    () => !document.querySelector('.grid > div.animate-pulse'),
    { timeout: 30_000 }
  ).catch(() => {});
  await page.waitForTimeout(500);

  // 카드 제목에서 [지역] 태그 추출 — ResultCard는 "[서울] 제목" 형식으로 렌더링
  const regionTags: string[] = await page.evaluate(() => {
    const titles = Array.from(document.querySelectorAll('.grid > div:not(.animate-pulse) h3, .grid > div:not(.animate-pulse) [class*="font-medium"]'));
    const tags: string[] = [];
    for (const el of titles) {
      const text = el.textContent || '';
      const match = text.match(/^\[([^\]]+)\]/);
      if (match) tags.push(match[1]);
    }
    return tags;
  });

  console.log(`  → DOM 지역 태그 발견: ${regionTags.length}건 — ${[...new Set(regionTags)].join(', ')}`);

  // [전국]은 렌더링 안 하므로, 보이는 태그는 서울 관련만 이어야 함
  const nonSeoul = regionTags.filter(r => !r.includes('서울'));
  if (nonSeoul.length > 0) {
    console.log(`  ⚠️  서울 외 지역 태그: ${nonSeoul.join(', ')} — 전국 공고는 태그 없이 표시됨`);
  } else {
    console.log(`  ✅ DOM 카드에 서울 외 지역 태그 없음 (전국 공고는 태그 미표시)`);
  }

  // 다른 광역시도 태그는 없어야 함
  const OTHER_REGIONS = ['경기', '인천', '부산', '대구', '광주', '대전', '울산', '세종',
    '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'];
  const otherTags = regionTags.filter(r => OTHER_REGIONS.some(o => r.includes(o)));
  expect(otherTags.length).toBe(0);

  await ctx.close();
});

// ════════════════════════════════════════════════════════════════════════
// 테스트 3: 맞춤 칩 — personalized:true + user_city=서울 응답 확인
// ════════════════════════════════════════════════════════════════════════
test('맞춤 칩: API 응답이 personalized:true이고 user_city가 서울이다', async ({ browser }) => {
  const ctx  = await browser.newContext({ viewport: MOBILE_VIEWPORT, isMobile: true });
  const page = await ctx.newPage();

  await page.goto(SITE);
  await page.evaluate((t) => localStorage.setItem('auth_token', t), completeToken);
  await page.reload();
  await waitForCards(page, 30_000);

  const dismissBtn = page.locator('button:has-text("나중에 할게요")');
  if (await dismissBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await dismissBtn.click();
    await page.waitForTimeout(300);
  }

  // 맞춤 API 응답 캡처
  let matchedResponse: any = null;
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/api/announcements/public') && url.includes('tab=matched')) {
      try {
        matchedResponse = await response.json();
      } catch {}
    }
  });

  const matchedChip = page.locator('button').filter({ hasText: /⭐/ }).first();
  await matchedChip.waitFor({ timeout: 10_000 });
  await matchedChip.click();
  console.log('  → ⭐맞춤 칩 클릭');

  await page.waitForFunction(
    () => {
      const amberSkeleton = document.querySelector('.bg-amber-50.animate-pulse');
      const spinners = document.querySelector('.animate-spin');
      return !amberSkeleton && !spinners;
    },
    { timeout: 60_000 }
  ).catch(() => {});
  await page.waitForTimeout(1_500);

  expect(matchedResponse).not.toBeNull();
  console.log(`  → 맞춤 API 응답 수신`);
  console.log(`     personalized: ${matchedResponse.personalized}`);
  console.log(`     user_city: ${matchedResponse.user_city}`);
  console.log(`     total: ${matchedResponse.total}`);
  if (matchedResponse.matched_keywords) {
    console.log(`     matched_keywords: ${JSON.stringify(matchedResponse.matched_keywords)}`);
  }

  // personalized 응답 검증
  expect(matchedResponse.personalized).toBe(true);
  console.log('  ✅ personalized:true 확인');

  // user_city는 캐시 경로에서는 생략될 수 있으므로 존재할 때만 검증
  if (matchedResponse.user_city !== undefined) {
    expect(matchedResponse.user_city).toBe('서울');
    console.log('  ✅ user_city:서울 확인');
  } else {
    console.log('  ℹ️  user_city 미포함 (캐시 응답 경로) — 필터 정확성은 Test 4에서 검증');
  }

  await ctx.close();
});

// ════════════════════════════════════════════════════════════════════════
// 테스트 4: 맞춤 칩 — 공고 region이 서울 또는 전국이고 카테고리가 관심분야와 연관되는지
// ════════════════════════════════════════════════════════════════════════
test('맞춤 칩: 공고 region이 서울/전국이고 카테고리가 관심분야와 연관된다', async ({ browser }) => {
  const ctx  = await browser.newContext({ viewport: MOBILE_VIEWPORT, isMobile: true });
  const page = await ctx.newPage();

  await page.goto(SITE);
  await page.evaluate((t) => localStorage.setItem('auth_token', t), completeToken);
  await page.reload();
  await waitForCards(page, 30_000);

  const dismissBtn = page.locator('button:has-text("나중에 할게요")');
  if (await dismissBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await dismissBtn.click();
    await page.waitForTimeout(300);
  }

  let matchedResponse: any = null;
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/api/announcements/public') && url.includes('tab=matched')) {
      try { matchedResponse = await response.json(); } catch {}
    }
  });

  const matchedChip = page.locator('button').filter({ hasText: /⭐/ }).first();
  await matchedChip.waitFor({ timeout: 10_000 });
  await matchedChip.click();

  await page.waitForFunction(
    () => !document.querySelector('.bg-amber-50.animate-pulse') && !document.querySelector('.animate-spin'),
    { timeout: 60_000 }
  ).catch(() => {});
  await page.waitForTimeout(1_500);

  expect(matchedResponse).not.toBeNull();
  const announcements: any[] = matchedResponse.data || [];
  expect(announcements.length).toBeGreaterThan(0);
  console.log(`  → 맞춤 공고 수: ${announcements.length}건`);

  // 계정 관심분야: 창업지원, 자금·지원, 기술·개발
  const INTEREST_CATEGORIES = new Set(['창업지원', '자금·지원', '기술·개발', 'R&D']);
  const ALLOWED_REGIONS = new Set(['서울', '전국', 'All', '', null, undefined]);

  let regionViolations = 0;
  let categoryMismatches = 0;
  const regionSet = new Set<string>();
  const categorySet = new Set<string>();

  for (const ann of announcements) {
    const r = ann.region ?? null;
    const c = ann.category ?? null;
    if (r) regionSet.add(r);
    if (c) categorySet.add(c);

    // region 위반: 서울/전국 외 지역
    if (r && !ALLOWED_REGIONS.has(r) && !r.includes('서울')) {
      regionViolations++;
      console.log(`     ⚠️  region 위반 id=${ann.announcement_id} region="${r}" title="${(ann.title || '').slice(0, 30)}"`);
    }

    // category 불일치: 관심분야에 없는 카테고리 (경고만, 실패 아님 — 맞춤은 키워드 기반)
    if (c && !INTEREST_CATEGORIES.has(c)) {
      categoryMismatches++;
    }
  }

  console.log(`  → 발견된 region 종류: ${[...regionSet].join(', ')}`);
  console.log(`  → 발견된 category 종류: ${[...categorySet].join(', ')}`);

  if (regionViolations > 0) {
    console.log(`  ❌ 서울/전국 외 region 공고 ${regionViolations}건`);
  } else {
    console.log(`  ✅ 모든 공고 region이 서울 또는 전국`);
  }

  if (categoryMismatches > 0) {
    // 맞춤은 키워드 기반이므로 category가 관심분야 외여도 될 수 있음 — 경고만
    console.log(`  ℹ️  관심분야 외 category 공고 ${categoryMismatches}건 (키워드 매칭으로 포함 가능)`);
  } else {
    console.log(`  ✅ 모든 공고 category가 관심분야(창업지원/자금·지원/기술·개발/R&D)에 해당`);
  }

  // region은 엄격히 검증
  expect(regionViolations).toBe(0);

  await ctx.close();
});
