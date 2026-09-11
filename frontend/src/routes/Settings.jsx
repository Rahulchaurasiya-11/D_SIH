import clsx from 'clsx';
import { Check, Monitor, Moon, Sun } from 'lucide-react';
import { useState } from 'react';

import { Badge, Button, Card, CardBody, CardHeader, Field, Input } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/I18nContext';
import { useTheme } from '../context/ThemeContext';
import { getApiBaseUrl, setApiBaseUrl } from '../lib/api';

const THEMES = [
  { id: 'light', icon: Sun, key: 'settings.themeLight' },
  { id: 'dark', icon: Moon, key: 'settings.themeDark' },
  { id: 'system', icon: Monitor, key: 'settings.themeSystem' },
];

export default function Settings() {
  const { t, language, setLanguage, languages, meta } = useI18n();
  const { mode, setMode } = useTheme();
  const { user } = useAuth();

  const [apiUrl, setApiUrl] = useState(getApiBaseUrl());
  const [saved, setSaved] = useState(false);

  const saveApiUrl = () => {
    setApiBaseUrl(apiUrl.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{t('settings.title')}</h1>
      </header>

      <Card>
        <CardHeader title={t('settings.account')} />
        <CardBody>
          <dl className="divide-y divide-line">
            {[
              [t('auth.fullName'), user?.full_name],
              [t('auth.email'), user?.email],
              [t('users.role'), t(`role.${user?.role}`)],
              [t('auth.designation'), user?.designation],
              [t('auth.jurisdiction'), user?.jurisdiction],
            ]
              .filter(([, value]) => value)
              .map(([label, value]) => (
                <div key={label} className="grid gap-1 py-3 sm:grid-cols-[1fr_1.6fr] sm:gap-4">
                  <dt className="text-[13px] text-muted">{label}</dt>
                  <dd className="text-sm text-ink">{value}</dd>
                </div>
              ))}
          </dl>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={t('settings.appearance')} />
        <CardBody>
          <div className="grid grid-cols-3 gap-2">
            {THEMES.map(({ id, icon: Icon, key }) => (
              <button
                key={id}
                onClick={() => setMode(id)}
                className={clsx(
                  'flex flex-col items-center gap-2 rounded-lg border p-4 transition-colors',
                  mode === id
                    ? 'border-brand bg-brand-soft text-brand'
                    : 'border-line text-muted hover:border-brand/40 hover:text-ink',
                )}
              >
                <Icon className="h-5 w-5" aria-hidden />
                <span className="text-[13px] font-medium">{t(key)}</span>
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={t('settings.language')} />
        <CardBody className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-2">
            {languages.map((lang) => (
              <button
                key={lang.code}
                onClick={() => setLanguage(lang.code)}
                className={clsx(
                  'flex items-center justify-between gap-3 rounded border px-3.5 py-2.5 text-left transition-colors',
                  language === lang.code
                    ? 'border-brand bg-brand-soft'
                    : 'border-line hover:border-brand/40',
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-ink">{lang.nativeName}</span>
                  <span className="block truncate text-[12px] text-faint">
                    {lang.name} · {lang.script}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  {!lang.complete && <Badge tone="warn">Partial</Badge>}
                  {language === lang.code && <Check className="h-4 w-4 text-brand" aria-hidden />}
                </span>
              </button>
            ))}
          </div>

          {!meta.complete && (
            <p className="rounded border border-warn/25 bg-warn-soft px-3.5 py-3 text-[13px] leading-relaxed text-warn">
              {t('settings.languageIncomplete')}
            </p>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={t('settings.connection')} />
        <CardBody>
          <Field label={t('settings.apiUrl')} hint={t('settings.apiUrlHelp')} htmlFor="api-url">
            <div className="flex gap-2">
              <Input
                id="api-url"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="http://localhost:8000"
                className="font-mono text-[13px]"
              />
              <Button variant="secondary" onClick={saveApiUrl}>
                {saved ? t('common.saved') : t('settings.save')}
              </Button>
            </div>
          </Field>
        </CardBody>
      </Card>
    </div>
  );
}
