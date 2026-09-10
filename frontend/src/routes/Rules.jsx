import { CheckCircle2, RefreshCw, Scale, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Skeleton,
  severityTone,
} from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/I18nContext';
import { api } from '../lib/api';

function money(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `₹${number.toLocaleString('en-IN')}` : '—';
}

export default function Rules() {
  const { t } = useI18n();
  const { hasRole } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloading, setReloading] = useState(false);
  const [flash, setFlash] = useState('');

  const load = () => {
    setLoading(true);
    api.rules
      .database()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const reload = async () => {
    setReloading(true);
    setError('');
    try {
      await api.rules.reload();
      setFlash(t('rules.reloaded'));
      setTimeout(() => setFlash(''), 3000);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setReloading(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="mx-auto max-w-5xl space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
    );
  }

  const rules = data?.master_rules ?? [];
  const prohibited = Object.entries(data?.prohibited_units ?? {});

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-ink">{t('rules.title')}</h1>
          <p className="mt-1 text-sm text-muted">{t('rules.subtitle')}</p>
        </div>
        {hasRole('ADMIN') && (
          <Button variant="secondary" icon={RefreshCw} loading={reloading} onClick={reload}>
            {t('rules.reload')}
          </Button>
        )}
      </header>

      {flash && (
        <p className="rounded border border-ok/25 bg-ok-soft px-3.5 py-3 text-[13px] text-ok">{flash}</p>
      )}
      <ErrorNote onRetry={load} retryLabel={t('common.retry')}>
        {error}
      </ErrorNote>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="p-4">
          <p className="text-[13px] text-muted">Statutory rules</p>
          <p className="tnum mt-1.5 text-[26px] font-semibold text-ink">{rules.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[13px] text-muted">{t('rules.approvedUnits')}</p>
          <p className="tnum mt-1.5 text-[26px] font-semibold text-ok">{data?.approved_units_count ?? 0}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[13px] text-muted">{t('rules.prohibitedUnits')}</p>
          <p className="tnum mt-1.5 text-[26px] font-semibold text-bad">{data?.prohibited_units_count ?? 0}</p>
        </Card>
      </div>

      <div className="space-y-3">
        {rules.map((rule) => (
          <Card key={rule.rule_id} className="p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Scale className="h-4 w-4 shrink-0 text-brand" aria-hidden />
                  <h2 className="text-[15px] font-semibold text-ink">{rule.rule_name}</h2>
                  <Badge tone={severityTone(rule.severity)}>{rule.severity}</Badge>
                  {String(rule.is_mandatory).toLowerCase() === 'true' && (
                    <Badge tone="brand">{t('rules.mandatory')}</Badge>
                  )}
                </div>
                <p className="mt-1 text-[12px] text-faint">{rule.legal_act_section}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-[11px] uppercase tracking-wide text-faint">{t('rules.penalty')}</p>
                <p className="tnum text-[13px] font-semibold text-ink">
                  {money(rule.penalty_min_inr)} – {money(rule.penalty_max_inr)}
                </p>
              </div>
            </div>

            <p className="mt-3 text-[13px] leading-relaxed text-muted">{rule.description}</p>

            {rule.remediation && (
              <p className="mt-3 rounded border border-line bg-raised/50 px-3.5 py-2.5 text-[13px] leading-relaxed text-muted">
                <span className="font-medium text-ink">Remedy: </span>
                {rule.remediation}
              </p>
            )}
          </Card>
        ))}
      </div>

      {prohibited.length > 0 && (
        <Card>
          <CardHeader
            title={t('rules.prohibitedUnits')}
            subtitle="Non-metric units that trigger a contravention under Rule 11"
          />
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {prohibited.map(([unit]) => (
                <span
                  key={unit}
                  className="inline-flex items-center gap-1.5 rounded border border-bad/25 bg-bad-soft px-2.5 py-1 font-mono text-[12px] text-bad"
                >
                  <XCircle className="h-3 w-3" aria-hidden />
                  {unit}
                </span>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {(data?.approved_units ?? []).length > 0 && (
        <Card>
          <CardHeader
            title={t('rules.approvedUnits')}
            subtitle="Approved SI and count units, including regional scripts"
          />
          <CardBody>
            <div className="flex flex-wrap gap-1.5">
              {data.approved_units.slice(0, 60).map((row, index) => (
                <span
                  key={`${row.unit_symbol || row.unit || index}`}
                  className="inline-flex items-center gap-1.5 rounded bg-ok-soft px-2 py-0.5 font-mono text-[12px] text-ok"
                >
                  <CheckCircle2 className="h-3 w-3" aria-hidden />
                  {row.unit_symbol || row.unit || Object.values(row)[0]}
                </span>
              ))}
              {data.approved_units.length > 60 && (
                <span className="px-2 py-0.5 text-[12px] text-faint">
                  +{data.approved_units.length - 60} more
                </span>
              )}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
