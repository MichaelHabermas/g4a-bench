import { test, expect } from '@playwright/test';

test('home lists runs and navigates to scorecard', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Choose a run' })).toBeVisible();
  const link = page.locator('a').filter({ hasText: '20260527T182321Z-static-prototype' }).first();
  await link.click();
  await expect(page.getByRole('heading', { name: /20260527T182321Z-static-prototype/ })).toBeVisible();
  await expect(page.getByText('verified').first()).toBeVisible({ timeout: 15000 });
});

test('chat panel opens', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Open chat' }).click();
  await expect(page.getByText('Yardstick chat')).toBeVisible();
});
