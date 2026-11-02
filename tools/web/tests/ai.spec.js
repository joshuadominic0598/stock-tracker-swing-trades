import { test, expect } from '@playwright/test';

async function mockModels(page) {
  await page.route('**/api/models', (route) =>
    route.fulfill({
      json: {
        default_provider: 'local',
        models: [],
        available: false,
        providers: {
          local: { configured: false, models: [], installed_models: [], default_model: 'qwen3:8b' },
          groq: {
            configured: false,
            models: [{ id: 'openai/gpt-oss-20b', label: 'GPT-OSS 20B', free_tier: true }],
            default_model: 'openai/gpt-oss-20b',
          },
          gemini: { configured: false, models: [], default_model: 'gemini-3.5-flash-lite' },
          openai: { configured: false, models: [], default_model: 'gpt-5-mini' },
        },
      },
    }),
  );
}

test('stock analysis starts with a plain-language view and three focused sections', async ({
  page,
}) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await mockModels(page);
  await page.route('**/api/research/**', (route) => route.fulfill({ json: {} }));
  await page.goto('/#asset/TCS');
  await page.locator('[data-action=research-tab][data-value=ai]').click();
  await expect(page.locator('.plain-overview h3')).toBeVisible();
  await expect(page.locator('[data-analysis-section]')).toHaveCount(3);
  await expect(page.locator('[data-analysis-section=news]')).toContainText('What the news says');
  await expect(page.locator('[data-analysis-section=attention]')).toContainText(
    'Google search trend not measured',
  );
  await expect(page.locator('.plain-flag-counts')).toContainText('green flags');
  await page
    .locator('#research-content')
    .screenshot({ path: '../../.tmp/plain-stock-analysis-desktop.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  expect(errors).toEqual([]);
  await page
    .locator('#research-content')
    .screenshot({ path: '../../.tmp/plain-stock-analysis.png' });
});

test('a newly typed key is saved before testing and changed settings cannot show stale success', async ({
  page,
}) => {
  await mockModels(page);
  const saved = [];
  await page.route('**/api/connections', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    saved.push(route.request().postDataJSON());
    await route.fulfill({ json: { groq_api_key_configured: true } });
  });
  await page.route('**/api/connections/check', (route) =>
    route.fulfill({ json: { ok: true, message: 'Model access checked.' } }),
  );
  await page.goto('/#settings');
  const card = page.locator('.provider-card[data-provider=groq]');
  const input = card.locator('[name=groq_api_key]');
  const remove = card.locator('[name=clear_groq_api_key]');
  await card.locator('details > summary').click();
  await remove.check();
  await input.fill('fixture-key');
  await expect(remove).not.toBeChecked();
  await card.getByRole('button', { name: 'Save & check connection' }).click();
  await expect(card.locator('[data-connection-status]')).toHaveText('Model access checked.');
  expect(saved[0].groq_api_key).toBe('fixture-key');
  expect(saved[0].clear_groq_api_key).toBe(false);
  expect(saved[0].groq_model).toBe('openai/gpt-oss-20b');
  await expect(input).toHaveValue('');

  await page.unroute('**/api/connections/check');
  let release, started;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const checking = new Promise((resolve) => {
    started = resolve;
  });
  await page.route('**/api/connections/check', async (route) => {
    started();
    await gate;
    await route.fulfill({ json: { ok: true, message: 'Model access checked.' } });
  });
  await card.getByRole('button', { name: 'Save & check connection' }).click();
  await checking;
  await input.fill('changed-fixture-key');
  release();
  await expect(card.locator('[data-connection-status]')).toContainText(
    'Settings changed during the check',
  );
  await expect(card.locator('.connection-status.positive')).toHaveCount(0);
  await expect(input).toHaveValue('changed-fixture-key');
});
