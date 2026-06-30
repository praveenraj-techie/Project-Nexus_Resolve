import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: {
    timeout: 20_000,
  },
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5175',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: '.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002',
      cwd: '../../services/backend',
      env: {
        ...process.env,
        APP_MODE: 'mock',
      },
      url: 'http://127.0.0.1:8002/api/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5175',
      env: {
        ...process.env,
        VITE_API_BASE: 'http://127.0.0.1:8002',
      },
      url: 'http://127.0.0.1:5175',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'python -m http.server 5176 --bind 127.0.0.1',
      cwd: '../..',
      url: 'http://127.0.0.1:5176/apps/deep-dive/',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
