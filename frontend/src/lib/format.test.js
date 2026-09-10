import { describe, expect, it } from 'vitest';

import { formatBytes, formatDate, formatDateTime, ruleLabel, statusLabel, todayISO } from './format';

describe('ruleLabel', () => {
  it('names every rule id the engine can emit', () => {
    // Kept in step with `grep '"rule_id": "' compliance_engine.py`. A chart axis
    // showing RULE_11_12_PROHIBITED_UNIT is unreadable to an officer.
    const emitted = [
      'RULE_11_12', 'RULE_11_12_NET_QUANTITY', 'RULE_11_12_NO_VALID_METRIC',
      'RULE_11_12_PROHIBITED_IMPERIAL', 'RULE_11_12_PROHIBITED_UNIT',
      'RULE_6_10_ORIGIN', 'RULE_6_10_ORIGIN_ADVISORY', 'RULE_6_1_A_MFG_NAME',
      'RULE_6_1_C', 'RULE_6_1_C_MISSING_DATE', 'RULE_6_1_C_UNREADABLE_DATE',
      'RULE_6_1_DA', 'RULE_6_1_DA_MISSING', 'RULE_6_1_DA_TAX_SUFFIX_MISSING',
      'RULE_6_1_G', 'RULE_6_1_G_CARE', 'RULE_6_1_G_EMAIL_MISSING',
      'RULE_6_1_G_HELPLINE_MISSING', 'RULE_6_1_G_MISSING_ALL',
      'RULE_9', 'RULE_9_FONT_SIZE_WARNING', 'RULE_9_LAYOUT',
    ];

    const unmapped = emitted.filter((id) => ruleLabel(id).includes('_'));
    expect(unmapped).toEqual([]);
  });

  it('degrades readably for an id it has never seen', () => {
    expect(ruleLabel('RULE_99_SOMETHING_NEW')).not.toContain('_');
  });

  it('handles an absent id', () => {
    expect(ruleLabel('')).toBe('—');
    expect(ruleLabel(undefined)).toBe('—');
  });
});

describe('formatDate', () => {
  it('formats an ISO timestamp', () => {
    expect(formatDate('2026-09-10T14:30:00Z')).toMatch(/2026/);
  });

  it('returns a dash rather than "Invalid Date" for empty input', () => {
    expect(formatDate('')).toBe('—');
    expect(formatDate(null)).toBe('—');
  });

  it('passes an unparseable value through instead of showing NaN', () => {
    expect(formatDate('not a date')).toBe('not a date');
  });

  it('includes a time when asked', () => {
    expect(formatDateTime('2026-09-10T14:30:00Z')).not.toBe(formatDate('2026-09-10T14:30:00Z'));
  });
});

describe('statusLabel', () => {
  const t = (key) => key;

  it('maps each status to its own key', () => {
    expect(statusLabel('COMPLIANT', t)).toBe('result.compliant');
    expect(statusLabel('PARTIALLY_COMPLIANT', t)).toBe('result.partial');
    expect(statusLabel('NON_COMPLIANT', t)).toBe('result.nonCompliant');
  });

  it('treats an unknown status as non-compliant rather than as compliant', () => {
    // Failing open would mark an unrecognised verdict as lawful.
    expect(statusLabel('SOMETHING_ELSE', t)).toBe('result.nonCompliant');
  });
});

describe('formatBytes', () => {
  it('scales units', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
  });

  it('handles zero and absent values', () => {
    expect(formatBytes(0)).toBe('—');
    expect(formatBytes(undefined)).toBe('—');
  });
});

describe('todayISO', () => {
  it('returns a date-input-compatible value', () => {
    expect(todayISO()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
