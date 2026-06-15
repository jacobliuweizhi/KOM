import { describe, expect, test } from 'vitest';
import { getTerm, termDefinitions } from '../data/termDefinitions';

describe('Glossary term definitions', () => {
  test('all core terms have definitions', () => {
    for (const term of termDefinitions) {
      expect(term.definition.length).toBeGreaterThanOrEqual(20);
      expect(term.chinese.length).toBeGreaterThan(2);
    }
  });

  test('naive RAG baseline has complete definition', () => {
    const term = getTerm('naive RAG baseline');
    expect(term?.definition).toContain('单阶段向量相似度 top-k 检索');
    expect(term?.definition).toContain('不使用指南锚点');
  });

  test('safety-critical error has complete definition', () => {
    const term = getTerm('safety-critical error');
    expect(term?.definition).toContain('实质性伤害');
    expect(term?.definition).toContain('关键安全门控');
  });

  test('physician-task prescription record has complete definition', () => {
    const term = getTerm('physician–task prescription record');
    expect(term?.definition).toContain('780');
    expect(term?.definition).toContain('不是 780 名医生');
  });
});
