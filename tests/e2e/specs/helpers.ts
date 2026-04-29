import { Page, expect, request } from "@playwright/test";

export const TEST_EMAIL = "test@naver.com";
export const TEST_PASSWORD = "111111";
export const BASE_URL = "http://localhost:3000";
export const API_URL = "http://localhost:8000";

/** storageState로 토큰이 이미 주입됨. 홈 화면으로 이동해 앱 초기화 */
export async function loginViaAPI(page: Page) {
  await page.goto(BASE_URL);
  await page.waitForLoadState("networkidle");

  // storageState에서 토큰이 없는 경우(예외상황) — API 호출 fallback
  const existing = await page.evaluate(() => localStorage.getItem("auth_token"));
  if (!existing) {
    const apiCtx = await request.newContext({ baseURL: API_URL });
    const res = await apiCtx.post("/api/auth/login", {
      data: { email: TEST_EMAIL, password: TEST_PASSWORD },
    });
    if (!res.ok()) throw new Error(`Login failed: ${res.status()} ${await res.text()}`);
    const { token } = await res.json();
    await apiCtx.dispose();
    await page.evaluate((tok) => localStorage.setItem("auth_token", tok), token);
    await page.reload();
    await page.waitForLoadState("networkidle");
  }
}

/** PRO 대시보드 열기 */
export async function openProDashboard(page: Page) {
  // planStatus 로드될 때까지 FAB 버튼 대기 (AI 지원사업 상담 버튼)
  await page.waitForSelector('[aria-label="AI 지원사업 상담"]', { timeout: 15000 });
  // FAB 클릭 → AiChatBot 열기 (PRO 플랜이면 ProSecretary 직행)
  await page.click('[aria-label="AI 지원사업 상담"]');
  // ProSecretary 헤더 대기
  await expect(page.getByText("전문가 대시보드").first()).toBeVisible({ timeout: 15000 });
}

/** ① 고객 선택 화면 확인 */
export async function expectClientSelectScreen(page: Page) {
  await expect(page.locator("text=누구의 상담을 시작하시겠습니까")).toBeVisible({ timeout: 8000 });
}

/** ③ 상담 목적 화면 확인 */
export async function expectConsultTypeScreen(page: Page) {
  await expect(page.locator("text=오늘 어떤 상담을 진행하시겠습니까")).toBeVisible({ timeout: 8000 });
}

/** 신규 사업자 폼에서 최소 입력 후 제출 */
export async function fillAndSubmitNewBizForm(page: Page, companyName = "테스트기업(주)") {
  // 첫 번째 input에 기업명 입력
  await page.locator("input").first().fill(companyName);
  // 지역 버튼 (서울) 클릭 — 없으면 skip
  const seoulBtn = page.locator("button").filter({ hasText: /^서울$/ }).first();
  if (await seoulBtn.isVisible({ timeout: 2000 }).catch(() => false)) await seoulBtn.click();
  // 제출
  const submitBtn = page.locator("button").filter({ hasText: /상담 시작|제출|다음/ }).first();
  await submitBtn.click();
}

/** AI 응답이 채팅에 표시될 때까지 대기 (최대 90초) */
export async function waitForAIMessage(page: Page) {
  await page.waitForFunction(
    () => document.querySelectorAll("[class*=rounded-bl-md], [class*=bubble]").length > 0,
    { timeout: 90000 }
  );
}
