import { expect, test } from '@playwright/test';

test('live workflow reaches approval, RCA, policy block, and audit export', async ({ page }) => {
  await page.goto('/#/incident/');

  await expect(page.getByText('NEXUS-RESOLVE')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Priority And Team Sorted Incidents' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Sort alerts' })).toHaveValue('priority');

  await page.goto('/#/incident/disk-space');

  await expect(page.getByText('Protected-Resource Block Demo')).not.toBeVisible();
  await expect(page.getByLabel('Audit export downloads')).toContainText('PDF Report Pending');

  await page.getByRole('button', { name: 'Live' }).click();
  await page.getByRole('button', { name: 'Start', exact: true }).click();

  await expect(page.getByText('Protected-Resource Block Demo')).toBeVisible();
  await expect(page.getByText('Plan touches protected resources and cannot continue.')).not.toBeVisible();
  await expect(page.locator('.status-strip strong')).toHaveText('Waiting approval', {
    timeout: 45_000,
  });
  await expect(page.getByLabel('ITSM command center')).toContainText('Teams Bridge');
  await expect(page.getByLabel('ITSM command center')).toContainText('Initial ISINFO');
  await expect(page.getByLabel('ITSM command center')).toContainText('P1/P2 only');
  await expect(page.getByRole('button', { name: 'Approve send Teams bridge draft' })).toHaveCount(0);
  await expect(page.locator('.status-strip strong')).toHaveText('Waiting approval');

  const approvalControls = page.getByLabel('Approval controls');
  await expect(approvalControls.getByRole('button', { name: 'Approve', exact: true })).toBeEnabled();
  await approvalControls.getByRole('button', { name: 'Approve', exact: true }).click();
  await expect(page.locator('.status-strip strong')).toHaveText('Waiting closure', {
    timeout: 45_000,
  });
  await expect(page.getByLabel('Audit export downloads')).toContainText('PDF Report');
  await page.getByRole('button', { name: 'Preview Note' }).click();
  await expect(page.getByLabel('Audit export downloads')).toContainText('dry_run: INC-2026-00421');

  await page.getByRole('button', { name: 'Show Real Block' }).click();
  await expect(page.getByText('Plan touches protected resources and cannot continue.')).toBeVisible();
});

test('security exception replay ends with rejection proof', async ({ page }) => {
  await page.goto('/#/incident/endpoint-third-party-app-exception');

  await expect(
    page.getByRole('heading', { name: 'Third-party application detected on endpoint' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Start Simulation' }).click();

  await expect(
    page.getByLabel('Agent Timeline').getByText(/Operator rejected automatic removal/),
  ).toBeVisible({
    timeout: 45_000,
  });
  await expect(page.locator('.status-strip strong').filter({ hasText: 'Rejected' })).toBeVisible();
  await expect(page.getByLabel('Ticket Details').getByText('RemoteAssistX')).toBeVisible();
});

test('deep-dive both-screen judge console renders backend evidence', async ({ page }) => {
  await page.goto('http://127.0.0.1:5176/apps/deep-dive/#both');

  await expect(page.getByText('Judge Console')).toBeVisible();
  await page.getByRole('tab', { name: /Both Screens/ }).click();
  await expect(page.getByRole('region', { name: /Frontend and backend moving together/ })).toBeVisible();
  await expect(page.getByText('Backend: API + CLI')).toBeVisible();
});

test('local SNOW desk mirrors run records, work notes, CI, and comms actions', async ({
  page,
}) => {
  const started = await page.request.post('http://127.0.0.1:8002/api/incidents', {
    data: { scenario_id: 'command-centre-alert-storm' },
  });
  expect(started.ok()).toBeTruthy();
  const { run_id: runId } = (await started.json()) as { run_id: string };

  await page.goto(
    `http://127.0.0.1:5176/apps/local-snow/?api=http://127.0.0.1:8002&run=${runId}`,
  );

  await expect(page.getByText('NEXUS ITSM Desk')).toBeVisible();

  await expect(
    page.getByRole('heading', { name: /INC-2026-00430 - Duplicate alert storm/ }),
  ).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText('CI / Site / Service')).toBeVisible();
  await expect(
    page.getByLabel('CMDB and CI site').getByText('Global NOC / Monitoring Core'),
  ).toBeVisible();
  await expect(
    page.getByLabel('NEXUS event stream').getByText('ticket.received'),
  ).toBeVisible({ timeout: 45_000 });
  await expect(page.getByRole('cell', { name: 'Problem' })).toBeVisible({
    timeout: 45_000,
  });

  const teamsBridge = page.locator('.comms-card').filter({ hasText: 'Teams bridge draft' });
  await expect(teamsBridge.getByRole('button', { name: 'Approve Send' })).toBeVisible();
  await teamsBridge.getByRole('button', { name: 'Approve Send' }).click();
  await expect(teamsBridge).toContainText('sent', { timeout: 20_000 });
  await expect(page.getByLabel('NEXUS event stream').getByText('comms.sent')).toBeVisible();
});
