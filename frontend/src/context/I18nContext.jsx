import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import en from '../locales/en.json';

const I18nContext = createContext(null);
const STORAGE_KEY = 'lm.language';

/**
 * Languages offered in the UI.
 *
 * `complete: true` means a full locale file ships for it. The others fall back to
 * English per missing key rather than showing a blank or a raw key - the settings
 * screen says so explicitly instead of pretending the translation is finished.
 * To complete one, add `src/locales/<code>.json` and flip the flag.
 */
export const LANGUAGES = [
  { code: 'en', name: 'English', nativeName: 'English', script: 'Latin', complete: true },
  { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी', script: 'Devanagari', complete: true },
  { code: 'mr', name: 'Marathi', nativeName: 'मराठी', script: 'Devanagari', complete: false },
  { code: 'bn', name: 'Bengali', nativeName: 'বাংলা', script: 'Bengali', complete: false },
  { code: 'te', name: 'Telugu', nativeName: 'తెలుగు', script: 'Telugu', complete: false },
  { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்', script: 'Tamil', complete: false },
  { code: 'gu', name: 'Gujarati', nativeName: 'ગુજરાતી', script: 'Gujarati', complete: false },
  { code: 'kn', name: 'Kannada', nativeName: 'ಕನ್ನಡ', script: 'Kannada', complete: false },
  { code: 'ml', name: 'Malayalam', nativeName: 'മലയാളം', script: 'Malayalam', complete: false },
  { code: 'pa', name: 'Punjabi', nativeName: 'ਪੰਜਾਬੀ', script: 'Gurmukhi', complete: false },
  { code: 'or', name: 'Odia', nativeName: 'ଓଡ଼ିଆ', script: 'Odia', complete: false },
  { code: 'as', name: 'Assamese', nativeName: 'অসমীয়া', script: 'Bengali', complete: false },
  { code: 'ur', name: 'Urdu', nativeName: 'اردو', script: 'Arabic', complete: false, rtl: true },
];

// Locale files are bundled lazily, so adding a language costs nothing until used.
// English is excluded because it is imported statically above as the fallback;
// globbing it too would pull it out of its own chunk and warn at build time.
const loaders = import.meta.glob(['../locales/*.json', '!../locales/en.json']);

function readStored() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return LANGUAGES.some((l) => l.code === value) ? value : 'en';
  } catch {
    return 'en';
  }
}

export function I18nProvider({ children }) {
  const [language, setLanguageState] = useState(readStored);
  const [messages, setMessages] = useState(en);

  useEffect(() => {
    let cancelled = false;

    if (language === 'en') {
      setMessages(en);
    } else {
      const load = loaders[`../locales/${language}.json`];
      if (load) {
        load().then((module) => {
          // Merge over English so an untranslated key renders readable text.
          if (!cancelled) setMessages({ ...en, ...(module.default ?? module) });
        });
      } else {
        setMessages(en);
      }
    }

    const meta = LANGUAGES.find((l) => l.code === language);
    document.documentElement.lang = language;
    document.documentElement.dir = meta?.rtl ? 'rtl' : 'ltr';

    return () => {
      cancelled = true;
    };
  }, [language]);

  const setLanguage = useCallback((code) => {
    setLanguageState(code);
    try {
      localStorage.setItem(STORAGE_KEY, code);
    } catch {
      /* private browsing - the choice still applies for this session */
    }
  }, []);

  /** t('repo.results', { total: 12 }) - falls back to the key so nothing renders blank. */
  const t = useCallback(
    (key, vars) => {
      let text = messages[key] ?? en[key] ?? key;
      if (vars) {
        Object.entries(vars).forEach(([name, value]) => {
          text = text.replace(new RegExp(`\\{${name}\\}`, 'g'), String(value));
        });
      }
      return text;
    },
    [messages],
  );

  const value = useMemo(
    () => ({
      t,
      language,
      setLanguage,
      languages: LANGUAGES,
      meta: LANGUAGES.find((l) => l.code === language) ?? LANGUAGES[0],
    }),
    [t, language, setLanguage],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) throw new Error('useI18n must be used inside <I18nProvider>');
  return context;
}
