import { fileURLToPath } from 'node:url';
import { test, expect } from '@playwright/test';

test('a fresh workspace exposes flags, ranked candidates and private AI choices', async ({
  page,
}) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/api/research/**', (route) =>
    route.fulfill({
      json: {
        fundamentals: { available: false },
        news: { available: false, articles: [] },
        social_sentiment: { available: false },
        search_interest: { available: false },
      },
    }),
  );
  await page.route('**/api/models', (route) =>
    route.fulfill({
      json: {
        default_provider: 'local',
        models: [],
        available: false,
        providers: {
          local: { configured: false, models: [], installed_models: [], default_model: 'qwen3:8b' },
          gemini: { configured: false, models: [], default_model: 'gemini-3.5-flash-lite' },
          openai: { configured: false, models: [], default_model: 'gpt-5-mini' },
          groq: { configured: false, models: [], default_model: 'openai/gpt-oss-20b' },
        },
      },
    }),
  );
  await page.goto('/#candidates');
  await expect(page).toHaveTitle('Swing Signal — Your market workspace');
  await expect(page.locator('.brand')).toContainText('Swing Signal');
  await expect(page.locator('.candidate-card').first()).toBeVisible();
  const scores = await page.locator('.candidate-score > strong').allTextContents();
  const values = scores.map((text) => parseFloat(text));
  expect(values).toEqual([...values].sort((a, b) => b - a));
  await expect(page.locator('.candidate-rank').first()).toHaveText('#1');
  await expect(page.locator('.trend-periods').first()).toBeVisible();
  if (process.env.SIGNALDESK_SCREENSHOTS === '1') {
    await page.screenshot({
      path: fileURLToPath(new URL('../../../docs/images/long-candidates.png', import.meta.url)),
    });
  }
  await page.goto('/#asset/TCS');
  await expect(page.locator('#chart-area canvas').first()).toBeVisible();
  await page.locator('.signal-details > summary').click();
  await expect(page.locator('.signal-tile')).toHaveCount(8);
  await expect(page.locator('.signal-tile .trend-period')).toHaveCount(3);
  await page.goto('/#holdings');
  await expect(page.locator('.holding-summary > div').first()).toContainText('0');
  await page.goto('/#settings');
  await expect(page.locator('.provider-card')).toHaveCount(4);
  await expect(page.locator('[name=local_model]')).toHaveValue('qwen3:8b');
  await expect(page.locator('[data-action=import-pick]')).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  expect(errors).toEqual([]);
});
