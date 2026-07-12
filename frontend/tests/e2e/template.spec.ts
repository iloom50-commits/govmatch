/**
 * 표준 E2E 테스트 템플릿
 *
 * 새 기능 테스트 시 이 파일을 복사해서 사용:
 *   cp tests/e2e/template.spec.ts tests/e2e/my_feature_test.spec.ts
 *
 * 실행:
 *   npx playwright test tests/e2e/my_feature_test.spec.ts --reporter=line
 *   npx playwright test tests/e2e/my_feature_test.spec.ts --headed   ← 브라우저 직접 확인
 */

import { test, expect } from "@playwright/test";
import {
  BASE_URL,
  LITE_TEST_TOKEN,
  loginAndGo,
  dismissProfileNudge,
  jsClick,
  logVisibleButtons,
} from "./helpers/auth";

test.use({ viewport: { width: 1280, height: 900 } });

// ── 비로그인 ─────────────────────────────────────────────────────────────────
test.describe("비로그인", () => {
  test("메인화면 정상 로드", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    await expect(page).toHaveTitle(/지원금AI/);
  });
});

// ── 로그인 ────────────────────────────────────────────────────────────────────
test.describe("로그인 (LITE 계정)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGo(page, LITE_TEST_TOKEN);
    await dismissProfileNudge(page);
  });

  test("대시보드 탭 노출 확인", async ({ page }) => {
    await expect(page.getByRole("button", { name: /기업 지원금/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /개인 지원금/ })).toBeVisible();
  });

  // ── 새 기능 테스트 여기에 추가 ──────────────────────────────────────────
  //
  // 예시 패턴:
  //
  // test("기능명 — 정상 동작", async ({ page }) => {
  //   // 1. 진입 경로 (버튼 클릭, URL 이동 등)
  //   await jsClick(page, "버튼텍스트");        // isVisible() false인 버튼은 jsClick 사용
  //   await page.waitForTimeout(1000);
  //
  //   // 2. 결과 검증
  //   await expect(page.locator("text=예상텍스트")).toBeVisible();
  //
  //   // 3. 모르겠으면 버튼 목록 출력 후 확인
  //   await logVisibleButtons(page);
  // });
  //
  // ────────────────────────────────────────────────────────────────────────
});

// ── 디버그 (실패 시 버튼 목록 확인) ──────────────────────────────────────────
test.describe("디버그", () => {
  test("로그인 후 버튼 목록 출력", async ({ page }) => {
    await loginAndGo(page, LITE_TEST_TOKEN);
    await dismissProfileNudge(page);
    await logVisibleButtons(page);
  });
});
