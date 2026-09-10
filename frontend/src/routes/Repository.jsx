import clsx from 'clsx';
import { FileSpreadsheet, Search, SlidersHorizontal, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Select,
  Skeleton,
  statusTone,
} from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/I18nContext';
import { api } from '../lib/api';
import { formatDate, ruleLabel, statusLabel, todayISO } from '../lib/format';

const EMPTY_FILTERS = {
  q: '', status: '', rule: '', date_from: '', date_to: '',
  min_score: '', max_score: '', source: '',
};

const RULES = [
  'RULE_6_1_DA_MISSING',
  'RULE_6_1_DA_TAX_SUFFIX_MISSING',
  'RULE_11_12_NET_QTY',
  'RULE_6_1_G_MISSING_ALL',
  'RULE_6_1_G_EMAIL_MISSING',
  'RULE_6_1_G_HELPLINE_MISSING',
  'RULE_6_1_C_MISSING_DATE',
  'RULE_6_1_C_UNREADABLE_DATE',
  'RULE_9_FONT_SIZE',
  'RULE_6_10_ORIGIN',
];

export default function Repository() {
  const { t } = useI18n();
  const { hasRole } = useAuth();

  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Debounce the free-text box; the rest apply on change.
  useEffect(() => {
    const timer = setTimeout(() => {
      setApplied(filters);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [filters]);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    api.inspections
      .search({ ...applied, page, page_size: 20 })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [applied, page]);

  useEffect(load, [load]);

  const set = (key) => (event) => setFilters((prev) => ({ ...prev, [key]: event.target.value }));
  const activeCount = Object.entries(applied).filter(([k, v]) => k !== 'q' && v).length;

  const exportAll = async () => {
    setExporting(true);
    try {
      await api.reports.bulk(applied);
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  };

  const items = data?.items ?? [];
  const noFilters = activeCount === 0 && !applied.q;

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-ink">{t('repo.title')}</h1>
          <p className="mt-1 text-sm text-muted">{t('repo.subtitle')}</p>
        </div>
        {hasRole('SENIOR_OFFICER') && items.length > 0 && (
          <Button variant="secondary" icon={FileSpreadsheet} loading={exporting} onClick={exportAll}>
            {t('repo.exportAll')}
          </Button>
        )}
      </header>

      <Card>
        <CardBody className="space-y-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
                aria-hidden
              />
              <Input
                value={filters.q}
                onChange={set('q')}
                placeholder={t('repo.search')}
                className="pl-9"
                aria-label={t('repo.search')}
              />
            </div>
            <Button
              variant={showFilters || activeCount ? 'subtle' : 'secondary'}
              icon={SlidersHorizontal}
              onClick={() => setShowFilters((v) => !v)}
            >
              {t('repo.filters')}
              {activeCount > 0 && <Badge tone="brand">{activeCount}</Badge>}
            </Button>
          </div>

          {showFilters && (
            <div className="animate-fade-up space-y-4 border-t border-line pt-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Field label={t('repo.status')}>
                  <Select value={filters.status} onChange={set('status')}>
                    <option value="">{t('common.all')}</option>
                    <option value="COMPLIANT">{t('result.compliant')}</option>
                    <option value="NON_COMPLIANT">{t('result.nonCompliant')}</option>
                  </Select>
                </Field>

                <Field label={t('repo.rule')}>
                  <Select value={filters.rule} onChange={set('rule')}>
                    <option value="">{t('common.all')}</option>
                    {RULES.map((rule) => (
                      <option key={rule} value={rule}>
                        {ruleLabel(rule)}
                      </option>
                    ))}
                  </Select>
                </Field>

                <Field label={t('repo.source')}>
                  <Select value={filters.source} onChange={set('source')}>
                    <option value="">{t('common.all')}</option>
                    <option value="image">Package photos</option>
                    <option value="manual">Typed label</option>
                    <option value="listing">E-commerce listing</option>
                    <option value="browser-ocr">Browser OCR</option>
                  </Select>
                </Field>

                <div className="grid grid-cols-2 gap-2">
                  <Field label={t('repo.minScore')}>
                    <Input type="number" min={0} max={100} value={filters.min_score} onChange={set('min_score')} />
                  </Field>
                  <Field label={t('repo.maxScore')}>
                    <Input type="number" min={0} max={100} value={filters.max_score} onChange={set('max_score')} />
                  </Field>
                </div>

                <Field label={t('repo.from')}>
                  <Input type="date" max={todayISO()} value={filters.date_from} onChange={set('date_from')} />
                </Field>
                <Field label={t('repo.to')}>
                  <Input type="date" max={todayISO()} value={filters.date_to} onChange={set('date_to')} />
                </Field>
              </div>

              {(activeCount > 0 || filters.q) && (
                <Button variant="ghost" size="sm" icon={X} onClick={() => setFilters(EMPTY_FILTERS)}>
                  {t('repo.clear')}
                </Button>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      <ErrorNote onRetry={load} retryLabel={t('common.retry')}>
        {error}
      </ErrorNote>

      {loading && !data ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon={Search}
            title={noFilters ? t('repo.emptyFirst') : t('repo.empty')}
            action={
              noFilters ? (
                <Link to="/scan">
                  <Button>{t('nav.scan')}</Button>
                </Link>
              ) : (
                <Button variant="secondary" onClick={() => setFilters(EMPTY_FILTERS)}>
                  {t('repo.clear')}
                </Button>
              )
            }
          />
        </Card>
      ) : (
        <>
          <p className="text-[13px] text-muted">{t('repo.results', { total: data.total })}</p>

          {/* Table on wide screens, cards on phones — a 7-column table is unusable at 375px. */}
          <Card className="hidden overflow-hidden lg:block">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-[12px] uppercase tracking-wide text-faint">
                    <th className="px-5 py-3 font-medium">Product</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium text-right">Score</th>
                    <th className="px-5 py-3 font-medium text-right">Issues</th>
                    {hasRole('SENIOR_OFFICER') && <th className="px-5 py-3 font-medium">Officer</th>}
                    <th className="px-5 py-3 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {items.map((row) => (
                    <tr key={row.id} className="transition-colors hover:bg-raised">
                      <td className="px-5 py-3">
                        <Link to={`/inspections/${row.id}`} className="font-medium text-ink hover:text-brand">
                          {row.product_name}
                        </Link>
                        <p className="text-[12px] text-faint">{row.brand || row.source}</p>
                      </td>
                      <td className="px-5 py-3">
                        <Badge tone={statusTone(row.status)}>{statusLabel(row.status, t)}</Badge>
                      </td>
                      <td className="tnum px-5 py-3 text-right font-medium text-ink">{row.overall_score}</td>
                      <td className="tnum px-5 py-3 text-right text-muted">{row.violations_count}</td>
                      {hasRole('SENIOR_OFFICER') && (
                        <td className="px-5 py-3 text-muted">{row.officer_name || '—'}</td>
                      )}
                      <td className="whitespace-nowrap px-5 py-3 text-muted">{formatDate(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="space-y-2 lg:hidden">
            {items.map((row) => (
              <Link key={row.id} to={`/inspections/${row.id}`} className="block">
                <Card className="card-interactive p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink">{row.product_name}</p>
                      <p className="mt-0.5 text-[12px] text-faint">
                        {row.brand || row.source} · {formatDate(row.created_at)}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1.5">
                      <Badge tone={statusTone(row.status)}>{statusLabel(row.status, t)}</Badge>
                      <span className="tnum text-[13px] font-semibold text-ink">{row.overall_score}/100</span>
                    </div>
                  </div>
                </Card>
              </Link>
            ))}
          </div>

          {data.pages > 1 && (
            <div className="flex items-center justify-between gap-3">
              <Button
                variant="secondary" size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                {t('common.previous')}
              </Button>
              <span className="tnum text-[13px] text-muted">
                {t('common.page')} {page} {t('common.of')} {data.pages}
              </span>
              <Button
                variant="secondary" size="sm"
                disabled={page >= data.pages}
                onClick={() => setPage((p) => p + 1)}
              >
                {t('common.next')}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
