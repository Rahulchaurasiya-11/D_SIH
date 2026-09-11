import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import en from '../locales/en.json';
import hi from '../locales/hi.json';
import { I18nProvider, LANGUAGES, useI18n } from './I18nContext';

const wrapper = ({ children }) => <I18nProvider>{children}</I18nProvider>;

describe('locale files', () => {
  it('every language marked complete has a full locale file', () => {
    const complete = LANGUAGES.filter((l) => l.complete).map((l) => l.code);
    expect(complete).toEqual(['en', 'hi']);

    // Claiming a language is complete while keys are missing would show English
    // to an officer who explicitly chose Hindi.
    const missing = Object.keys(en).filter((key) => !(key in hi));
    expect(missing).toEqual([]);
  });

  it('has no Hindi keys that English lacks', () => {
    // A stray key here means dead weight, or an English string someone deleted
    // without cleaning up the translations.
    const orphans = Object.keys(hi).filter((key) => !(key in en));
    expect(orphans).toEqual([]);
  });

  it('leaves no value blank', () => {
    for (const [locale, name] of [[en, 'en'], [hi, 'hi']]) {
      const blank = Object.entries(locale)
        .filter(([, value]) => !String(value).trim())
        .map(([key]) => key);
      expect(blank, `${name} has blank values`).toEqual([]);
    }
  });

  it('keeps every placeholder that English declares', () => {
    // Dropping {days} from a translation renders the literal braces to the user.
    const placeholders = (text) => (String(text).match(/\{\w+\}/g) ?? []).sort();
    const mismatched = Object.keys(en).filter(
      (key) => key in hi && placeholders(en[key]).join() !== placeholders(hi[key]).join(),
    );
    expect(mismatched).toEqual([]);
  });

  it('lists every language exactly once', () => {
    const codes = LANGUAGES.map((l) => l.code);
    expect(new Set(codes).size).toBe(codes.length);
  });
});

describe('useI18n', () => {
  it('returns English by default', async () => {
    const { result } = renderHook(() => useI18n(), { wrapper });
    await waitFor(() => expect(result.current.t('nav.dashboard')).toBe(en['nav.dashboard']));
  });

  it('substitutes named placeholders', async () => {
    const { result } = renderHook(() => useI18n(), { wrapper });
    await waitFor(() =>
      expect(result.current.t('dashboard.window', { days: 30 })).toContain('30'),
    );
    expect(result.current.t('dashboard.window', { days: 30 })).not.toContain('{days}');
  });

  it('falls back to the key rather than rendering nothing', async () => {
    const { result } = renderHook(() => useI18n(), { wrapper });
    await waitFor(() => expect(result.current.t('no.such.key')).toBe('no.such.key'));
  });

  it('switches language and falls back per key for partial locales', async () => {
    const { result } = renderHook(() => useI18n(), { wrapper });

    await waitFor(() => expect(result.current.t('nav.dashboard')).toBe(en['nav.dashboard']));

    await act(async () => {
      result.current.setLanguage('hi');
    });
    await waitFor(() => expect(result.current.t('nav.dashboard')).toBe(hi['nav.dashboard']));

    // Marathi ships no locale file, so it must read as English, not as blanks.
    await act(async () => {
      result.current.setLanguage('mr');
    });
    await waitFor(() => expect(result.current.t('nav.dashboard')).toBe(en['nav.dashboard']));
  });

  it('marks Urdu right-to-left', () => {
    expect(LANGUAGES.find((l) => l.code === 'ur').rtl).toBe(true);
    expect(LANGUAGES.filter((l) => l.rtl).map((l) => l.code)).toEqual(['ur']);
  });
});
