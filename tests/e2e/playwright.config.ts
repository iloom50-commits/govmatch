import { defineConfig } from "@playwright/test";
import path from "path";

export default defineConfig({
  testDir: "./specs",
  timeout: 60000,
  retries: 0,
  globalSetup: "./global-setup.ts",
  reporter: [["list"], ["html", { open: "never", outputFolder: "report" }]],
  use: {
    baseURL: "http://localhost:3000",
    storageState: path.join(__dirname, ".auth-state.json"),
    headless: false,          // 화면 보이게 실행
    slowMo: 400,              // 각 액션 400ms 딜레이 (흐름 확인용)
    viewport: { width: 1280, height: 800 },
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
});
