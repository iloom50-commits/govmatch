import { chromium, request } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

const TEST_EMAIL = "test@naver.com";
const TEST_PASSWORD = "111111";
const BASE_URL = "http://localhost:3000";
const API_URL = "http://localhost:8000";
const STORAGE_FILE = path.join(__dirname, ".auth-state.json");

export default async function globalSetup() {
  // API로 토큰 발급
  const apiCtx = await request.newContext({ baseURL: API_URL });
  const res = await apiCtx.post("/api/auth/login", {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
  });
  if (!res.ok()) throw new Error(`Global setup login failed: ${res.status()} ${await res.text()}`);
  const { token } = await res.json();
  await apiCtx.dispose();

  // 브라우저로 localStorage에 토큰 주입 후 storageState 저장
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(BASE_URL);
  await page.waitForLoadState("networkidle");
  await page.evaluate((tok) => localStorage.setItem("auth_token", tok), token);
  await context.storageState({ path: STORAGE_FILE });
  await browser.close();

  console.log(`[global-setup] 로그인 완료, storageState 저장: ${STORAGE_FILE}`);
}
