import { ScanLine, ShieldCheck, FileBarChart } from 'lucide-react';
import { useState } from 'react';

import { Button, ErrorNote, Field, Input } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/I18nContext';

const HIGHLIGHTS = [
  { icon: ScanLine, title: 'Scan any package', body: 'Up to four angles, read on device or on the server.' },
  { icon: ShieldCheck, title: 'Rules, not guesswork', body: 'Every finding cites its provision of the 2011 Rules.' },
  { icon: FileBarChart, title: 'Reports that issue', body: 'Printable PDF and an editable Word notice.' },
];

export default function Login() {
  const { t } = useI18n();
  const { signIn, register } = useAuth();

  const [mode, setMode] = useState('signin');
  const [form, setForm] = useState({
    email: '', password: '', full_name: '', designation: '', jurisdiction: '',
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const set = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'signin') await signIn(form.email, form.password);
      else await register(form);
    } catch (err) {
      setError(err.message || t('common.error'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen bg-canvas lg:grid-cols-[1.05fr_1fr]">
      {/* Identity panel. Hidden on phones so the form is above the fold. */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-brand p-12 text-brand-ink lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)',
            backgroundSize: '28px 28px',
          }}
          aria-hidden
        />

        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded bg-brand-ink/15" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7">
                <path
                  d="M12 3v18M5 8h14M7 8l-3 6a3 3 0 006 0L7 8zm10 0l-3 6a3 3 0 006 0l-3-6zM9 21h6"
                  stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold">{t('app.org')}</p>
              <p className="text-xs opacity-70">Government of India</p>
            </div>
          </div>

          <h1 className="mt-16 max-w-md text-[34px] font-semibold leading-[1.15] tracking-tight">
            {t('app.name')}
          </h1>
          <p className="mt-4 max-w-md text-[15px] leading-relaxed opacity-80">
            Check packaged commodities against the Legal Metrology (Packaged Commodities)
            Rules, 2011 — from a phone, in the shop.
          </p>
        </div>

        <ul className="relative space-y-5">
          {HIGHLIGHTS.map(({ icon: Icon, title, body }) => (
            <li key={title} className="flex gap-3.5">
              <Icon className="mt-0.5 h-5 w-5 shrink-0 opacity-80" aria-hidden />
              <div>
                <p className="text-sm font-medium">{title}</p>
                <p className="text-[13px] leading-relaxed opacity-70">{body}</p>
              </div>
            </li>
          ))}
        </ul>

        <p className="relative text-xs opacity-60">
          Legal Metrology Act, 2009 · Packaged Commodities Rules, 2011
        </p>
      </aside>

      {/* Form panel */}
      <main className="flex items-center justify-center px-5 py-12 sm:px-10">
        <div className="w-full max-w-sm animate-fade-up">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="grid h-10 w-10 place-items-center rounded bg-brand text-brand-ink" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
                <path
                  d="M12 3v18M5 8h14M7 8l-3 6a3 3 0 006 0L7 8zm10 0l-3 6a3 3 0 006 0l-3-6zM9 21h6"
                  stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-ink">{t('app.name')}</p>
              <p className="text-[11px] text-faint">{t('app.subtitle')}</p>
            </div>
          </div>

          <h2 className="text-[22px] font-semibold tracking-tight text-ink">
            {t(mode === 'signin' ? 'auth.signInTitle' : 'auth.registerTitle')}
          </h2>
          <p className="mt-1.5 text-sm text-muted">{t('auth.signInSubtitle')}</p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            {mode === 'register' && (
              <Field label={t('auth.fullName')} htmlFor="full_name">
                <Input
                  id="full_name" value={form.full_name} onChange={set('full_name')}
                  required minLength={2} autoComplete="name" placeholder="Ravi Kumar"
                />
              </Field>
            )}

            <Field label={t('auth.email')} htmlFor="email">
              <Input
                id="email" type="email" value={form.email} onChange={set('email')}
                required autoComplete="email" placeholder="officer@legalmetrology.gov.in"
              />
            </Field>

            <Field
              label={t('auth.password')}
              htmlFor="password"
              hint={mode === 'register' ? t('auth.passwordHint') : undefined}
            >
              <Input
                id="password" type="password" value={form.password} onChange={set('password')}
                required minLength={mode === 'register' ? 8 : undefined}
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                placeholder="••••••••"
              />
            </Field>

            {mode === 'register' && (
              <div className="grid grid-cols-2 gap-3">
                <Field label={t('auth.designation')} htmlFor="designation">
                  <Input id="designation" value={form.designation} onChange={set('designation')} placeholder="Inspector" />
                </Field>
                <Field label={t('auth.jurisdiction')} htmlFor="jurisdiction">
                  <Input id="jurisdiction" value={form.jurisdiction} onChange={set('jurisdiction')} placeholder="Delhi North" />
                </Field>
              </div>
            )}

            <ErrorNote>{error}</ErrorNote>

            <Button type="submit" size="lg" loading={busy} className="w-full">
              {busy ? t('auth.signingIn') : t(mode === 'signin' ? 'auth.signIn' : 'auth.register')}
            </Button>
          </form>

          <p className="mt-6 text-center text-[13px] text-muted">
            {t(mode === 'signin' ? 'auth.noAccount' : 'auth.haveAccount')}{' '}
            <button
              type="button"
              onClick={() => {
                setMode(mode === 'signin' ? 'register' : 'signin');
                setError('');
              }}
              className="font-semibold text-brand underline-offset-2 hover:underline"
            >
              {t(mode === 'signin' ? 'auth.register' : 'auth.signIn')}
            </button>
          </p>

          {mode === 'register' && (
            <p className="mt-4 rounded border border-line bg-raised px-3.5 py-3 text-[12px] leading-relaxed text-muted">
              {t('auth.firstAccountNote')}
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
