import { test, expect } from '@playwright/test';

const SITE = 'https://www.govmatch.kr';

test.setTimeout(60_000);

// ── 1. 홈페이지 SSR 공고 콘텐츠 노출 확인 (봇 시점) ──────────────────
test('[SEO] 홈페이지 — SSR 공고 카드 HTML에 포함됨', async ({ page }) => {
  // JavaScript 비활성화 → 봇과 동일한 환경
  await page.route('**/*.js', route => route.abort());
  await page.goto(SITE, { waitUntil: 'domcontentloaded', timeout: 30_000 });

  // SSR 섹션이 HTML에 존재해야 함
  const ssrSection = page.locator('.home-seo-section');
  await expect(ssrSection).toBeAttached({ timeout: 10_000 });

  // 공고 카드 최소 1개 이상 포함
  const cards = page.locator('.home-seo-section article');
  const cardCount = await cards.count();
  console.log(`\n══ [1] SSR 공고 카드 수: ${cardCount}개`);
  expect(cardCount).toBeGreaterThan(0);

  // h2 태그 존재 확인
  const h2 = page.locator('.home-seo-section h2').first();
  await expect(h2).toBeAttached();
  console.log(`   h2 텍스트: "${await h2.textContent()}"`);

  // 공고 링크 확인
  const firstLink = page.locator('.home-seo-section article a').first();
  const href = await firstLink.getAttribute('href');
  console.log(`   첫 번째 공고 링크: ${href}`);
  expect(href).toMatch(/\/announcements\/\d+/);
});

// ── 2. 홈페이지 메타 태그 확인 ─────────────────────────────────────
test('[SEO] 홈페이지 — 메타 description 키워드 포함', async ({ page }) => {
  await page.goto(SITE, { waitUntil: 'domcontentloaded', timeout: 30_000 });

  const title = await page.title();
  const description = await page.getAttribute('meta[name="description"]', 'content') || '';

  console.log(`\n══ [2] 메타태그 확인 ══`);
  console.log(`   title: ${title}`);
  console.log(`   description (${description.length}자): ${description.slice(0, 80)}...`);

  // 제목에 "지원금AI" 포함
  expect(title).toContain('지원금AI');
  // description이 충분한 길이 (20자 이상)
  expect(description.length).toBeGreaterThan(20);
  // description에 핵심 키워드 포함
  expect(description).toMatch(/지원금|보조금|정책자금/);
});

// ── 3. /search 페이지 — SSR 정적 콘텐츠 확인 ──────────────────────
test('[SEO] /search 페이지 — 정적 콘텐츠 및 h1 노출', async ({ page }) => {
  await page.route('**/*.js', route => route.abort());
  await page.goto(`${SITE}/search`, { waitUntil: 'domcontentloaded', timeout: 30_000 });

  const h1 = page.locator('h1').first();
  await expect(h1).toBeAttached({ timeout: 8_000 });
  const h1Text = await h1.textContent();
  console.log(`\n══ [3] /search 페이지 ══`);
  console.log(`   h1: "${h1Text}"`);
  expect(h1Text).toMatch(/검색|지원금/);

  // 인기 검색어 키워드 링크 확인
  const keywords = page.locator('a[href*="/?q="]');
  const kwCount = await keywords.count();
  console.log(`   키워드 링크 수: ${kwCount}개`);
  expect(kwCount).toBeGreaterThan(0);
});

// ── 4. 공고 상세 페이지 — SSR + BreadcrumbList 확인 ───────────────
test('[SEO] 공고 상세 페이지 — 구조화 데이터 및 h1 노출', async ({ page, request }) => {
  // 공개 공고 1건 가져오기
  const annRes = await request.get(
    'https://govmatch-production.up.railway.app/api/announcements/public?page=1&size=1&target_type=business'
  );
  const annData = await annRes.json();
  const ann = annData.data?.[0];
  if (!ann) { console.log('공고 없음 — 스킵'); return; }

  await page.route('**/*.js', route => route.abort());
  await page.goto(`${SITE}/announcements/${ann.announcement_id}`, {
    waitUntil: 'domcontentloaded',
    timeout: 30_000,
  });

  // h1 (공고 제목) 확인
  const h1 = page.locator('h1').first();
  await expect(h1).toBeAttached({ timeout: 8_000 });
  const h1Text = await h1.textContent();
  console.log(`\n══ [4] 공고 상세 — announcement_id: ${ann.announcement_id} ══`);
  console.log(`   h1: "${h1Text?.slice(0, 50)}"`);
  expect(h1Text?.length).toBeGreaterThan(3);

  // BreadcrumbList JSON-LD 스키마 확인
  const schemas = await page.evaluate(() => {
    const scripts = [...document.querySelectorAll('script[type="application/ld+json"]')];
    return scripts.map(s => { try { return JSON.parse(s.textContent || ''); } catch { return null; } }).filter(Boolean);
  });
  const breadcrumb = schemas.find((s: any) => s['@type'] === 'BreadcrumbList');
  console.log(`   BreadcrumbList: ${breadcrumb ? '✅ 있음' : '❌ 없음'}`);
  expect(breadcrumb).toBeTruthy();
});

// ── 5. 키워드 클릭 → 홈으로 이동 후 검색어 전달 확인 ────────────────
test('[SEO] /search 키워드 링크 클릭 → 홈 이동', async ({ page }) => {
  await page.goto(`${SITE}/search`, { waitUntil: 'networkidle', timeout: 30_000 });

  // JS 활성 상태에서 키워드 링크 클릭
  const firstKwLink = page.locator('a[href*="/?q="]').first();
  await expect(firstKwLink).toBeVisible({ timeout: 10_000 });
  const kwText = await firstKwLink.textContent();
  const href = await firstKwLink.getAttribute('href');
  console.log(`\n══ [5] 키워드 링크 클릭 ══`);
  console.log(`   키워드: "${kwText}" → ${href}`);

  await firstKwLink.click();
  await page.waitForURL('**/?q=**', { timeout: 10_000 });
  const finalUrl = page.url();
  console.log(`   최종 URL: ${finalUrl}`);
  expect(finalUrl).toContain('?q=');
});

// ── 6. 홈페이지 SSR 공고 링크 → 공고 상세 진입 확인 ─────────────────
test('[SEO] 홈 SSR 공고 링크 → 공고 상세 페이지 진입', async ({ page }) => {
  await page.goto(SITE, { waitUntil: 'networkidle', timeout: 40_000 });

  // SSR 섹션이 나타날 때까지 대기
  const ssrSection = page.locator('.home-seo-section');
  await expect(ssrSection).toBeVisible({ timeout: 15_000 });

  const firstAnnLink = page.locator('.home-seo-section article a').first();
  await expect(firstAnnLink).toBeVisible({ timeout: 5_000 });
  const annTitle = await firstAnnLink.textContent();
  const href = await firstAnnLink.getAttribute('href');
  console.log(`\n══ [6] SSR 공고 링크 클릭 ══`);
  console.log(`   공고: "${annTitle?.slice(0, 40)}" → ${href}`);

  await firstAnnLink.click();
  await page.waitForURL(`${SITE}/announcements/**`, { timeout: 15_000 });

  // 상세 페이지에서 h1 확인
  const h1 = page.locator('h1').first();
  await expect(h1).toBeVisible({ timeout: 10_000 });
  console.log(`   상세 h1: "${(await h1.textContent())?.slice(0, 50)}"`);
  expect(page.url()).toMatch(/\/announcements\/\d+/);
});
