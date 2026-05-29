import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'pnpm --filter @yardstick/server dev',
      port: 8787,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'pnpm --filter @yardstick/web dev',
      port: 5173,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
