import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  Gauge,
  Gavel,
  Repeat,
  ScanLine,
  Store,
  TrendingUp,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Area,
  AreaChart,
} from 'recharts';

import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Select,
  Skeleton,
  Stat,
  statusTone,
} from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/I18nContext';
import { api } from '../lib/api';
import { formatDate, ruleLabel } from '../lib/format';

const SEVERITY_COLOUR = {
  CRITICAL: 'rgb(var(--bad))',
  HIGH: 'rgb(var(--bad))',
  MEDIUM: 'rgb(var(--warn))',
  LOW: 'rgb(var(--faint))',
};

/** Recharts has no theme awareness, so chart chrome reads the tokens directly. */
const AXIS = { stroke: 'rgb(var(--faint))', fontSize: 11 };

// Recharts replays its entry animation on every re-render, which keeps the page
// repainting continuously and fights `prefers-reduced-motion`. The numbers are the
// point here, not the motion.
const NO_ANIM = { isAnimationActive: false };
const TOOLTIP_STYLE = {
  backgroundColor: 'rgb(var(--surface))',
  border: '1px solid rgb(var(--line))',
  borderRadius: 10,
  fontSize: 12,
  color: 'rgb(var(--ink))',
  boxShadow: '0 12px 32px rgb(var(--shadow) / 0.16)',
};

function ChartCard({ title, subtitle, children, action }) {
  return (
    <Card>
      <CardHeader title={title} subtitle={subtitle} action={action} />
      <CardBody className="pt-4">{children}</CardBody>
    </Card>
  );
}

export default function Dashboard() {
  const { t } = useI18n();
  const { user, hasRole } = useAuth();

  const [days, setDays] = useState(30);
  const [stats, setStats] = useState(null);
  const [offenders, setOffenders] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    api.dashboard
      .stats(days)
      .then((data) => !cancelled && setStats(data))
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));

    // Senior officers and above only; a 403 for an inspector is expected, not an error.
    api.dashboard
      .repeatOffenders(Math.max(days, 90))
      .then((data) => !cancelled && setOffenders(data.offenders ?? []))
      .catch(() => !cancelled && setOffenders([]));

    return () => {
      cancelled = true;
    };
  }, [days]);

  const trend = useMemo(
    () =>
      (stats?.trend ?? []).map((point) => ({
        ...point,
        label: point.date.slice(5),
      })),
    [stats],
  );

  const byRule = useMemo(
    () =>
      (stats?.violations_by_rule ?? []).slice(0, 7).map((row) => ({
        ...row,
        label: ruleLabel(row.rule_id),
      })),
    [stats],
  );

  const severity = useMemo(
    () => (stats?.severity_split ?? []).filter((row) => row.count > 0),
    [stats],
  );

  if (loading && !stats) {
    return (
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-[104px]" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-72 lg:col-span-2" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  const empty = stats && stats.total_inspections === 0;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-ink">{t('dashboard.title')}</h1>
          <p className="mt-1 text-sm text-muted">
            {t('dashboard.subtitle')} ·{' '}
            <span className="text-faint">
              {t(stats?.scope === 'own' ? 'dashboard.scopeOwn' : 'dashboard.scopeAll')}
            </span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Select value={days} onChange={(e) => setDays(Number(e.target.value))} className="w-40">
            <option value={7}>{t('dashboard.window', { days: 7 })}</option>
            <option value={30}>{t('dashboard.window', { days: 30 })}</option>
            <option value={90}>{t('dashboard.window', { days: 90 })}</option>
          </Select>
          <Link to="/scan">
            <Button icon={ScanLine}>{t('nav.scan')}</Button>
          </Link>
        </div>
      </header>

      <ErrorNote onRetry={() => setDays((d) => d)} retryLabel={t('common.retry')}>
        {error}
      </ErrorNote>

      {empty ? (
        <Card>
          <EmptyState
            icon={ScanLine}
            title={t('repo.emptyFirst')}
            description={t('scan.subtitle')}
            action={
              <Link to="/scan">
                <Button icon={ScanLine}>{t('nav.scan')}</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Stat label={t('dashboard.today')} value={stats.inspections_today} icon={CalendarDays} />
            <Stat label={t('dashboard.week')} value={stats.inspections_this_week} icon={TrendingUp} />
            <Stat
              label={t('dashboard.complianceRate')}
              value={`${stats.compliance_rate}%`}
              tone={stats.compliance_rate >= 70 ? 'ok' : stats.compliance_rate >= 40 ? 'warn' : 'bad'}
              sub={`${stats.compliant} ${t('common.of')} ${stats.total_inspections}`}
              icon={CheckCircle2}
            />
            <Stat
              label={t('dashboard.openViolations')}
              value={stats.total_violations}
              tone={stats.total_violations > 0 ? 'bad' : 'ok'}
              icon={AlertTriangle}
            />
            <Stat
              label={t('dashboard.averageScore')}
              value={stats.average_score}
              tone={stats.average_score >= 85 ? 'ok' : stats.average_score >= 60 ? 'warn' : 'bad'}
              sub="out of 100"
              icon={Gauge}
            />
          </div>

          {/* Enforcement activity. Detection is half the picture an official needs;
              the other half is what happened to the findings. */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat
              label={t('dashboard.openCases')}
              value={stats.open_cases ?? 0}
              tone={(stats.open_cases ?? 0) > 0 ? 'warn' : 'ok'}
              sub={`${stats.concluded_cases ?? 0} concluded`}
              icon={Gavel}
            />
            <Stat
              label={t('dashboard.recoveryRate')}
              value={`${stats.compliance_recovery_rate ?? 0}%`}
              tone={(stats.compliance_recovery_rate ?? 0) >= 60 ? 'ok' : 'warn'}
              sub="of concluded cases complied"
              icon={CheckCircle2}
            />
            <Stat
              label={t('dashboard.premisesCovered')}
              value={stats.premises_covered ?? 0}
              icon={Store}
            />
            <Card className="p-4">
              <p className="text-[13px] font-medium text-muted">{t('dashboard.caseActivity')}</p>
              <ul className="mt-2.5 space-y-1">
                {(stats.cases_by_status ?? [])
                  .filter((row) => row.count > 0)
                  .map((row) => (
                    <li key={row.case_status} className="flex items-center justify-between gap-2">
                      <span className="truncate text-[12px] text-muted">
                        {t(`case.${row.case_status}`)}
                      </span>
                      <span className="tnum text-[13px] font-semibold text-ink">{row.count}</span>
                    </li>
                  ))}
                {(stats.cases_by_status ?? []).every((row) => row.count === 0) && (
                  <li className="text-[12px] text-faint">{t('common.none')}</li>
                )}
              </ul>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <ChartCard title={t('dashboard.trend')} subtitle={t('dashboard.window', { days })}>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={trend} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                      <defs>
                        <linearGradient id="okFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="rgb(var(--ok))" stopOpacity={0.28} />
                          <stop offset="100%" stopColor="rgb(var(--ok))" stopOpacity={0.02} />
                        </linearGradient>
                        <linearGradient id="badFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="rgb(var(--bad))" stopOpacity={0.28} />
                          <stop offset="100%" stopColor="rgb(var(--bad))" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--line))" vertical={false} />
                      <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} />
                      <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={36} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: 'rgb(var(--line))' }} />
                      <Legend wrapperStyle={{ fontSize: 12, color: 'rgb(var(--muted))' }} iconType="circle" />
                      <Area
                        {...NO_ANIM}
                        type="monotone" dataKey="compliant" name={t('result.compliant')}
                        stroke="rgb(var(--ok))" strokeWidth={2} fill="url(#okFill)"
                      />
                      <Area
                        {...NO_ANIM}
                        type="monotone" dataKey="non_compliant" name={t('result.nonCompliant')}
                        stroke="rgb(var(--bad))" strokeWidth={2} fill="url(#badFill)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
            </div>

            <ChartCard title={t('dashboard.bySeverity')}>
              {severity.length === 0 ? (
                <EmptyState icon={CheckCircle2} title={t('result.noViolations')} className="py-10" />
              ) : (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        {...NO_ANIM}
                        data={severity} dataKey="count" nameKey="severity"
                        innerRadius="55%" outerRadius="80%" paddingAngle={2} strokeWidth={0}
                      >
                        {severity.map((row) => (
                          <Cell key={row.severity} fill={SEVERITY_COLOUR[row.severity] || 'rgb(var(--faint))'} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Legend wrapperStyle={{ fontSize: 12, color: 'rgb(var(--muted))' }} iconType="circle" />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </ChartCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title={t('dashboard.byRule')}>
              {byRule.length === 0 ? (
                <EmptyState icon={CheckCircle2} title={t('result.noViolations')} className="py-10" />
              ) : (
                <div style={{ height: Math.max(200, byRule.length * 38) }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={byRule} layout="vertical" margin={{ left: 8, right: 16 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--line))" horizontal={false} />
                      <XAxis type="number" tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
                      <YAxis
                        type="category" dataKey="label" tick={AXIS} tickLine={false}
                        axisLine={false} width={130}
                      />
                      <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgb(var(--raised))' }} />
                      <Bar
                        {...NO_ANIM}
                        dataKey="count" name={t('result.violations')}
                        fill="rgb(var(--brand))" radius={[0, 4, 4, 0]} barSize={16}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </ChartCard>

            <Card>
              <CardHeader title={t('dashboard.topBrands')} />
              <CardBody className="p-0">
                {(stats.top_offending_brands ?? []).length === 0 ? (
                  <EmptyState icon={CheckCircle2} title={t('common.none')} className="py-10" />
                ) : (
                  <ul className="divide-y divide-line">
                    {stats.top_offending_brands.map((row) => (
                      <li key={row.brand} className="flex items-center justify-between gap-4 px-5 py-3">
                        <span className="min-w-0 truncate text-sm text-ink">{row.brand}</span>
                        <span className="flex shrink-0 items-center gap-3">
                          <span className="text-[12px] text-faint">
                            {row.total} {row.total === 1 ? 'scan' : 'scans'}
                          </span>
                          <Badge tone={row.violations > 0 ? 'bad' : 'ok'}>{row.violations}</Badge>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          </div>

          {offenders.length > 0 && (
            <Card>
              <CardHeader
                title={
                  <span className="flex items-center gap-2">
                    <Repeat className="h-4 w-4 text-bad" aria-hidden />
                    {t('dashboard.repeatOffenders')}
                  </span>
                }
                subtitle={t('dashboard.repeatOffendersSub')}
              />
              <CardBody className="p-0">
                <ul className="divide-y divide-line">
                  {offenders.slice(0, 6).map((row) => (
                    <li key={row.brand} className="flex flex-wrap items-center gap-3 px-5 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-ink">{row.brand}</p>
                        <p className="text-[12px] text-faint">
                          {t('dashboard.inspectionsCount', { count: row.inspections })} ·{' '}
                          {t('dashboard.premisesCount', { count: row.distinct_premises })}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {(row.top_rules ?? []).map((rule) => (
                          <Badge key={rule.rule_id} tone="bad">
                            {ruleLabel(rule.rule_id)} ×{rule.count}
                          </Badge>
                        ))}
                      </div>
                      {row.open_cases > 0 && (
                        <Badge tone="warn">{row.open_cases} open</Badge>
                      )}
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader
              title={t('dashboard.recent')}
              action={
                <Link to="/repository" className="text-[13px] font-semibold text-brand hover:underline">
                  {t('nav.repository')}
                </Link>
              }
            />
            <CardBody className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-[12px] uppercase tracking-wide text-faint">
                      <th className="px-5 py-2.5 font-medium">Product</th>
                      <th className="px-5 py-2.5 font-medium">Status</th>
                      <th className="px-5 py-2.5 font-medium text-right">Score</th>
                      {hasRole('SENIOR_OFFICER') && <th className="px-5 py-2.5 font-medium">Officer</th>}
                      <th className="px-5 py-2.5 font-medium">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {stats.recent.map((row) => (
                      <tr key={row.id} className="transition-colors hover:bg-raised">
                        <td className="px-5 py-3">
                          <Link to={`/inspections/${row.id}`} className="font-medium text-ink hover:text-brand">
                            {row.product_name}
                          </Link>
                          {row.brand && <p className="text-[12px] text-faint">{row.brand}</p>}
                        </td>
                        <td className="px-5 py-3">
                          <Badge tone={statusTone(row.status)}>
                            {t(row.status === 'COMPLIANT' ? 'result.compliant' : 'result.nonCompliant')}
                          </Badge>
                        </td>
                        <td className="tnum px-5 py-3 text-right font-medium text-ink">{row.overall_score}</td>
                        {hasRole('SENIOR_OFFICER') && (
                          <td className="px-5 py-3 text-muted">{row.officer_name || '—'}</td>
                        )}
                        <td className="whitespace-nowrap px-5 py-3 text-muted">{formatDate(row.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}
