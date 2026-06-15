import type { DemoCase } from '../data/demoCases';

export function caseDisplayId(c: DemoCase) {
  const parts = c.id.split('-');
  return `Case ${parts[0]}-${parts[1]}`;
}

export const deidentificationNote =
  'Displayed case labels are de-identified standardized-case labels for reviewer inspection.';
