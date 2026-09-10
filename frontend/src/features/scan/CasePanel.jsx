import clsx from 'clsx';
import { Gavel, History, MapPin, Store } from 'lucide-react';
import { useState } from 'react';

import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Field,
  Input,
  Select,
  Textarea,
} from '../../components/ui';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import { api } from '../../lib/api';
import { formatDateTime } from '../../lib/format';
import { useSubmitGuard } from '../../lib/useSubmitGuard';

/** Mirrors CASE_TRANSITIONS on the server, which is the authority. */
const TRANSITIONS = {
  OPEN: ['NOTICE_ISSUED', 'CLOSED'],
  NOTICE_ISSUED: ['COMPLIED', 'ESCALATED', 'CLOSED'],
  COMPLIED: ['CLOSED'],
  ESCALATED: ['CLOSED'],
  CLOSED: [],
};

const TONE = {
  OPEN: 'warn',
  NOTICE_ISSUED: 'bad',
  COMPLIED: 'ok',
  ESCALATED: 'bad',
  CLOSED: 'neutral',
};

const DOT_COLOUR = {
  OPEN: 'bg-warn',
  NOTICE_ISSUED: 'bg-bad',
  COMPLIED: 'bg-ok',
  ESCALATED: 'bg-bad',
  CLOSED: 'bg-faint',
};

/**
 * The enforcement case attached to a non-compliant inspection.
 *
 * A scan produces a finding; enforcement is what happens next. Tracking that is
 * what makes the dashboard a record of activity rather than only of detection.
 */
export default function CasePanel({ inspection, onUpdated }) {
  const { t } = useI18n();
  const { hasRole } = useAuth();

  const [target, setTarget] = useState('');
  const [note, setNote] = useState('');
  const [noticeRef, setNoticeRef] = useState('');

  const status = inspection.case_status || '';
  const allowed = TRANSITIONS[status] ?? [];
  const canAct = hasRole('SENIOR_OFFICER') && allowed.length > 0;

  const hasPremises = Boolean(inspection.premises_name);
  const hasCoords = inspection.latitude != null && inspection.longitude != null;

  const [submitCase, busy, error] = useSubmitGuard(async () => {
    const updated = await api.inspections.updateCase(inspection.id, {
      case_status: target,
      note,
      notice_reference: noticeRef,
    });
    onUpdated(updated);
    setTarget('');
    setNote('');
    setNoticeRef('');
  });

  const submit = (event) => {
    event.preventDefault();
    if (!target) return;
    submitCase();
  };

  return (
    <div className="space-y-4">
      {/* Premises — where the pack was found */}
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Store className="h-4 w-4 text-brand" aria-hidden />
              {t('premises.title')}
            </span>
          }
        />
        <CardBody className="p-0">
          {hasPremises ? (
            <dl className="divide-y divide-line">
              {[
                [t('premises.name'), inspection.premises_name],
                [t('premises.address'), inspection.premises_address],
                [t('premises.type'), t(`premises.type${inspection.premises_type || 'OTHER'}`)],
                [t('premises.licence'), inspection.premises_licence],
                [t('premises.remarks'), inspection.remarks],
              ]
                .filter(([, v]) => v)
                .map(([label, value]) => (
                  <div key={label} className="grid gap-1 px-5 py-3 sm:grid-cols-[1fr_1.6fr] sm:gap-4">
                    <dt className="text-[13px] text-muted">{label}</dt>
                    <dd className="text-sm text-ink">{value}</dd>
                  </div>
                ))}
              {hasCoords && (
                <div className="grid gap-1 px-5 py-3 sm:grid-cols-[1fr_1.6fr] sm:gap-4">
                  <dt className="text-[13px] text-muted">Coordinates</dt>
                  <dd className="text-sm text-ink">
                    <a
                      href={`https://www.openstreetmap.org/?mlat=${inspection.latitude}&mlon=${inspection.longitude}#map=18/${inspection.latitude}/${inspection.longitude}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 font-mono text-[13px] text-brand hover:underline"
                    >
                      <MapPin className="h-3.5 w-3.5" aria-hidden />
                      {inspection.latitude.toFixed(5)}, {inspection.longitude.toFixed(5)}
                      {inspection.location_accuracy_m
                        ? ` (±${Math.round(inspection.location_accuracy_m)}m)`
                        : ''}
                    </a>
                  </dd>
                </div>
              )}
            </dl>
          ) : (
            <p className="px-5 py-4 text-[13px] leading-relaxed text-warn">
              {t('premises.missingWarning')}
            </p>
          )}
        </CardBody>
      </Card>

      {/* Enforcement case */}
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Gavel className="h-4 w-4 text-brand" aria-hidden />
              {t('case.title')}
            </span>
          }
          action={status ? <Badge tone={TONE[status]}>{t(`case.${status}`)}</Badge> : null}
        />
        <CardBody className="space-y-4">
          {!status ? (
            <p className="text-[13px] text-muted">{t('case.none')}</p>
          ) : (
            <>
              <dl className="grid gap-3 sm:grid-cols-2">
                <div>
                  <dt className="text-[12px] text-faint">{t('case.number')}</dt>
                  <dd className="font-mono text-sm font-semibold text-ink">
                    {inspection.case_number || '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-[12px] text-faint">{t('case.notice')}</dt>
                  <dd className="font-mono text-sm text-ink">
                    {inspection.notice_reference || '—'}
                  </dd>
                </div>
              </dl>

              {(inspection.case_history ?? []).length > 0 && (
                <div>
                  <p className="mb-2 flex items-center gap-1.5 text-[12px] font-medium uppercase tracking-wide text-faint">
                    <History className="h-3.5 w-3.5" aria-hidden />
                    {t('case.history')}
                  </p>
                  <ol className="space-y-2 border-l-2 border-line pl-4">
                    {inspection.case_history.map((entry, index) => (
                      <li key={index} className="relative">
                        {/* Written out, not interpolated: Tailwind scans source
                            statically, so a constructed class name is purged. */}
                        <span
                          className={clsx(
                            'absolute -left-[21px] top-1.5 h-2 w-2 rounded-full',
                            DOT_COLOUR[entry.to] ?? 'bg-faint',
                          )}
                          aria-hidden
                        />
                        <p className="text-[13px] text-ink">
                          {t(`case.${entry.from}`)} → <b>{t(`case.${entry.to}`)}</b>
                        </p>
                        <p className="text-[12px] text-faint">
                          {entry.by_name} · {formatDateTime(entry.at)}
                        </p>
                        {entry.note && (
                          <p className="mt-0.5 text-[12px] leading-relaxed text-muted">{entry.note}</p>
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {canAct ? (
                <form onSubmit={submit} className="space-y-3 border-t border-line pt-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label={t('case.advance')} htmlFor="case-target">
                      <Select id="case-target" value={target} onChange={(e) => setTarget(e.target.value)}>
                        <option value="">—</option>
                        {allowed.map((next) => (
                          <option key={next} value={next}>
                            {t(`case.${next}`)}
                          </option>
                        ))}
                      </Select>
                    </Field>

                    {target === 'NOTICE_ISSUED' && (
                      <Field label={t('case.noticeRef')} htmlFor="case-notice">
                        <Input
                          id="case-notice"
                          value={noticeRef}
                          onChange={(e) => setNoticeRef(e.target.value)}
                          placeholder="LM/NOT/2026/88"
                        />
                      </Field>
                    )}
                  </div>

                  <Field label={t('case.note')} htmlFor="case-note">
                    <Textarea
                      id="case-note"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      rows={2}
                      className="min-h-0"
                    />
                  </Field>

                  <ErrorNote>{error}</ErrorNote>

                  <Button type="submit" loading={busy} disabled={!target}>
                    {t('case.submit')}
                  </Button>
                </form>
              ) : (
                allowed.length > 0 && (
                  <p className="border-t border-line pt-4 text-[12px] text-faint">
                    Advancing a case requires senior officer privileges.
                  </p>
                )
              )}
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
