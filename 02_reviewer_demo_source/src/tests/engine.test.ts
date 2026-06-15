import { describe, expect, test } from 'vitest';
import { demoCases } from '../data/demoCases';
import { structuredProfile } from '../engine/profileEngine';
import { retrievalSummary, retrieveEvidence, retrieveNaiveEvidence } from '../engine/ragEngine';
import { safetyAudit } from '../engine/safetyEngine';
import { generatePrescription } from '../engine/prescriptionEngine';
import { scorePrescription } from '../engine/scoringEngine';
import { buildMarkdownReport } from '../engine/exportEngine';

describe('KOM engines', () => {
  test('profiles all cases', () => {
    for (const c of demoCases) {
      expect(structuredProfile(c).identity).toContain(String(c.age));
    }
  });

  test('RAG retrieves at least three evidence cards', () => {
    for (const c of demoCases) {
      expect(retrieveEvidence(c).length).toBeGreaterThanOrEqual(3);
    }
  });

  test('RAG returns KOM-RAG and naive RAG baseline groups', () => {
    const summary = retrievalSummary(demoCases[0]);
    expect(summary.topEvidence.length).toBeGreaterThan(0);
    expect(summary.naiveEvidence.length).toBeGreaterThan(0);
  });

  test('naive RAG baseline output is available without safety failure', () => {
    const naive = retrieveNaiveEvidence(demoCases.find(c => c.id === 'Q4-01-9304021')!);
    expect(naive.length).toBeGreaterThan(0);
    expect(naive.every(item => typeof item.guidelineAnchor === 'boolean')).toBe(true);
  });

  test('safety engine detects risk warnings or pass states', () => {
    const q4 = demoCases.find(c => c.quadrant === 'Q4')!;
    expect(['warning', 'critical']).toContain(safetyAudit(q4).status);
  });

  test('prescription contains required domains', () => {
    const rx = generatePrescription(demoCases[0]);
    expect(rx.exercise).toContain('FITT');
    expect(rx.medication).toBeTruthy();
    expect(rx.followUp).toContain('weeks');
    expect(rx.safetyNotes.length).toBeGreaterThan(0);
  });

  test('scoring range is bounded', () => {
    const score = scorePrescription(demoCases[0]);
    expect(score.overall).toBeGreaterThanOrEqual(0);
    expect(score.overall).toBeLessThanOrEqual(10);
  });

  test('export markdown includes module names', () => {
    const report = buildMarkdownReport(demoCases[0]);
    expect(report).toContain('KOM-Assess');
    expect(report).toContain('KOM-Treat');
    expect(report).toContain('KOM-RAG');
    expect(report).toContain('naive RAG baseline');
    expect(report).toContain('KOM-Safe');
  });
});
