import { expect, test } from '@playwright/test';

test('reviewer flow runs locally', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('KOM Reviewer Interface')).toBeVisible();
  await page.getByRole('button', { name: 'Case workspace' }).click();
  await page.getByTestId('case-card-Q4-01-9304021').click();
  await page.getByTestId('run-workflow').click();
  const main = page.locator('main');
  await expect(main.getByText('KOM-Assess').first()).toBeVisible();
  await expect(main.getByText('KOM-Treat / KOM-RAG evidence')).toBeVisible();
  await expect(main.getByText('KOM-Safe safety audit')).toBeVisible();
  await page.getByRole('button', { name: 'Results' }).click();
  await expect(page.getByText('Full KOM overall')).toBeVisible();
  await expect(page.getByText('8.46')).toBeVisible();
  await expect(page.getByText('Clinician + KOM overall')).toBeVisible();
  await expect(page.getByText('7.34')).toBeVisible();
  await expect(page.getByText('0.676 vs 0.303')).toBeVisible();
  await page.getByRole('button', { name: 'KOM-Treat' }).click();
  await expect(page.getByText('What is the naive RAG baseline?')).toBeVisible();
  await expect(page.getByText(/vector similarity only/)).toBeVisible();
  await page.getByRole('button', { name: 'KOM-Score' }).click();
  await expect(page.getByText(/Safety-critical error rate = number of safety-critical errors/)).toBeVisible();
  await expect(page.getByText(/may cause material patient harm/)).toBeVisible();
  await page.getByRole('button', { name: 'KOM-Sim' }).click();
  await page.getByTestId('sim-textarea').fill('Topical NSAID first, supervised exercise, weight support, and follow-up.');
  await page.getByRole('button', { name: 'Case workspace' }).click();
  await page.getByRole('button', { name: 'Download report' }).click();
});
