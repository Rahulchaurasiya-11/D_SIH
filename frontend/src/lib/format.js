/** Shared formatting helpers, so no two screens format the same value differently. */

export function formatDate(iso, { withTime = false } = {}) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  });
}

export function formatDateTime(iso) {
  return formatDate(iso, { withTime: true });
}

/**
 * Turns RULE_6_1_DA_TAX_SUFFIX_MISSING into "Rule 6(1)(da) · Tax suffix missing"
 * for axis labels and chips, where the raw identifier is unreadable.
 */
export function ruleLabel(ruleId) {
  if (!ruleId) return '—';

  // Every rule_id the engine can emit. Kept exhaustive so a chart axis never
  // falls back to a raw identifier like RULE_11_12_PROHIBITED_UNIT.
  const known = {
    RULE_6_1_A_MFG_NAME: 'Manufacturer details',
    RULE_6_1_C: 'Mfg date',
    RULE_6_1_C_MISSING_DATE: 'Mfg date missing',
    RULE_6_1_C_UNREADABLE_DATE: 'Mfg date unreadable',
    RULE_6_1_DA: 'MRP & tax suffix',
    RULE_6_1_DA_MISSING: 'MRP missing',
    RULE_6_1_DA_TAX_SUFFIX_MISSING: 'Tax suffix missing',
    RULE_6_1_G: 'Consumer care',
    RULE_6_1_G_CARE: 'Consumer care',
    RULE_6_1_G_EMAIL_MISSING: 'Care e-mail missing',
    RULE_6_1_G_HELPLINE_MISSING: 'Helpline missing',
    RULE_6_1_G_MISSING_ALL: 'No consumer care',
    RULE_6_10_ORIGIN: 'Country of origin',
    RULE_6_10_ORIGIN_ADVISORY: 'Origin advisory',
    RULE_9: 'Font & layout',
    RULE_9_FONT_SIZE: 'Font size',
    RULE_9_FONT_SIZE_WARNING: 'Font too small',
    RULE_9_LAYOUT: 'Layout',
    RULE_11_12: 'Net quantity',
    RULE_11_12_NET_QTY: 'Net quantity',
    RULE_11_12_NET_QUANTITY: 'Net quantity',
    RULE_11_12_NO_VALID_METRIC: 'No metric unit',
    RULE_11_12_PROHIBITED_IMPERIAL: 'Imperial unit used',
    RULE_11_12_PROHIBITED_UNIT: 'Imperial unit used',
  };
  if (known[ruleId]) return known[ruleId];

  return ruleId
    .replace(/^RULE_/, 'Rule ')
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/^rule/, 'Rule');
}

export function statusLabel(status, t) {
  if (status === 'COMPLIANT') return t('result.compliant');
  if (status === 'PARTIALLY_COMPLIANT') return t('result.partial');
  return t('result.nonCompliant');
}

export function formatBytes(bytes) {
  if (!bytes) return '—';
  const units = ['B', 'KB', 'MB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

/** Today's date as YYYY-MM-DD, for date-input maximums. */
export function todayISO() {
  return new Date().toISOString().slice(0, 10);
}
