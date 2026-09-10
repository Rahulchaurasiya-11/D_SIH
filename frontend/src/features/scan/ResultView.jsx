import clsx from 'clsx';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  FileDown,
  FileText,
  PencilLine,
  ScanLine,
  ShieldCheck,
} from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  ScoreRing,
  severityTone,
  statusTone,
} from '../../components/ui';
import { useI18n } from '../../context/I18nContext';
import { api } from '../../lib/api';
import { statusLabel } from '../../lib/format';
import EvidenceViewer from './EvidenceViewer';
import VerifyPanel from './VerifyPanel';

/** The mandatory declarations, in the order an officer reads a pack. */
const DECLARATIONS = [
  { key: 'manufacturer_name', label: 'Manufacturer / packer / importer', rule: 'Rule 6(1)(a)' },
  { key: 'net_quantity', label: 'Net quantity', rule: 'Rule 11 & 12', unit: 'unit_of_measure' },
  { key: 'mrp', label: 'Maximum Retail Price', rule: 'Rule 6(1)(da)', money: true },
  { key: 'manufacturing_date', label: 'Month & year of manufacture', rule: 'Rule 6(1)(c)' },
  { key: 'consumer_care_email', label: 'Consumer care e-mail', rule: 'Rule 6(1)(g)' },
  { key: 'consumer_care_phone', label: 'Consumer care telephone', rule: 'Rule 6(1)(g)' },
  { key: 'country_of_origin', label: 'Country of origin', rule: 'Rule 6(10)' },
  { key: 'batch_number', label: 'Batch / lot number', rule: 'Rule 6(1)(f)' },
];

function VerdictBanner({ result, t }) {
  const tone = statusTone(result.status);
  const bg = { ok: 'bg-ok-soft', warn: 'bg-warn-soft', bad: 'bg-bad-soft' }[tone];
  const fg = { ok: 'text-ok', warn: 'text-warn', bad: 'text-bad' }[tone];
  const Icon = tone === 'ok' ? ShieldCheck : AlertTriangle;

  return (
    <Card className={clsx('overflow-hidden border-0 p-0', bg)}>
      <div className="flex flex-col items-center gap-5 p-6 sm:flex-row sm:p-7">
        <ScoreRing score={result.overall_score} size={112} label={t('result.score')} />

        <div className="min-w-0 flex-1 text-center sm:text-left">
          <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
            <Icon className={clsx('h-5 w-5 shrink-0', fg)} aria-hidden />
            <h2 className={clsx('text-[22px] font-semibold tracking-tight', fg)}>
              {statusLabel(result.status, t)}
            </h2>
            {result.is_manually_verified && (
              <Badge tone="brand" icon={PencilLine}>
                {t('result.verifiedBadge')}
              </Badge>
            )}
          </div>

          <p className="mt-1.5 text-sm text-muted">
            {result.violations.length === 0
              ? t('result.noViolations')
              : `${result.violations.length} ${t('result.violations').toLowerCase()} · ${
                  result.passed_checks?.length ?? 0
                } ${t('result.passed').toLowerCase()}`}
          </p>

          {result.processing_time_ms && (
            <p className="mt-1 text-[12px] text-faint">
              {result.images_count ?? 1} image(s) · {Math.round(result.processing_time_ms)} ms ·{' '}
              {result.ocr_engine || result.ai_engine_used}
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}

function ViolationCard({ violation, t }) {
  const [open, setOpen] = useState(false);
  const tone = severityTone(violation.severity);
  const severity = String(violation.severity || 'MEDIUM').toUpperCase();

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 p-4 text-left transition-colors hover:bg-raised"
      >
        <AlertTriangle
          className={clsx('mt-0.5 h-4 w-4 shrink-0', tone === 'bad' ? 'text-bad' : 'text-warn')}
          aria-hidden
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">{violation.rule_name || violation.rule_id}</p>
            <Badge tone={tone}>{t(`severity.${severity}`)}</Badge>
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-muted">{violation.description}</p>
        </div>
        <ChevronDown
          className={clsx('mt-0.5 h-4 w-4 shrink-0 text-faint transition-transform', open && 'rotate-180')}
          aria-hidden
        />
      </button>

      {open && (
        <dl className="animate-fade-up space-y-3 border-t border-line bg-raised/40 px-4 py-4 text-[13px]">
          {[
            [t('result.legalReference'), violation.legal_reference],
            [t('result.foundText'), violation.found_text],
            [t('result.remediation'), violation.remediation],
          ]
            .filter(([, value]) => value)
            .map(([label, value]) => (
              <div key={label} className="grid gap-1 sm:grid-cols-[150px_1fr] sm:gap-4">
                <dt className="font-medium text-faint">{label}</dt>
                <dd className="leading-relaxed text-ink">{value}</dd>
              </div>
            ))}
        </dl>
      )}
    </div>
  );
}

export default function ResultView({ result, localFiles, onResultChange, onReset }) {
  const { t } = useI18n();
  const [tab, setTab] = useState('violations');
  const [verifying, setVerifying] = useState(false);
  const [downloading, setDownloading] = useState('');

  const meta = result.extracted_metadata || {};
  const violations = result.violations || [];
  const passed = result.passed_checks || [];

  const download = async (format) => {
    if (!result.inspection_id) return;
    setDownloading(format);
    try {
      await api.reports.download(result.inspection_id, format);
    } catch {
      /* the error surfaces in the button returning to rest */
    } finally {
      setDownloading('');
    }
  };

  const TABS = [
    { id: 'violations', label: t('result.violations'), count: violations.length, tone: 'bad' },
    { id: 'declarations', label: t('result.declarations') },
    { id: 'passed', label: t('result.passed'), count: passed.length, tone: 'ok' },
    { id: 'evidence', label: t('result.evidence') },
  ];

  return (
    <div className="space-y-5">
      <VerdictBanner result={result} t={t} />

      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" icon={ScanLine} onClick={onReset}>
          {t('result.newScan')}
        </Button>
        <Button variant="secondary" icon={PencilLine} onClick={() => setVerifying(true)}>
          {t('result.verify')}
        </Button>
        {result.inspection_id && (
          <>
            <Button
              variant="secondary"
              icon={FileDown}
              loading={downloading === 'pdf'}
              onClick={() => download('pdf')}
            >
              {t('detail.downloadPdf')}
            </Button>
            <Button
              variant="secondary"
              icon={FileText}
              loading={downloading === 'docx'}
              onClick={() => download('docx')}
            >
              {t('detail.downloadDocx')}
            </Button>
            <Link to={`/inspections/${result.inspection_id}`} className="ml-auto self-center">
              <span className="text-[13px] font-semibold text-brand hover:underline">
                {t('detail.title')} →
              </span>
            </Link>
          </>
        )}
      </div>

      <Card>
        <div className="flex gap-1 overflow-x-auto border-b border-line px-2">
          {TABS.map((item) => (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className={clsx(
                'relative shrink-0 px-3 py-3 text-[13px] font-medium transition-colors',
                tab === item.id ? 'text-brand' : 'text-muted hover:text-ink',
              )}
            >
              <span className="flex items-center gap-1.5">
                {item.label}
                {item.count !== undefined && item.count > 0 && (
                  <Badge tone={item.tone}>{item.count}</Badge>
                )}
              </span>
              {tab === item.id && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand" />}
            </button>
          ))}
        </div>

        <CardBody>
          {tab === 'violations' &&
            (violations.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-10 text-center">
                <CheckCircle2 className="h-10 w-10 text-ok" aria-hidden />
                <p className="max-w-md text-sm leading-relaxed text-muted">{t('result.noViolations')}</p>
              </div>
            ) : (
              <div className="space-y-3">
                {violations.map((violation, index) => (
                  <ViolationCard key={`${violation.rule_id}-${index}`} violation={violation} t={t} />
                ))}
              </div>
            ))}

          {tab === 'declarations' && (
            <dl className="divide-y divide-line">
              {DECLARATIONS.map((field) => {
                const raw = meta[field.key];
                const value = raw
                  ? field.unit && meta[field.unit]
                    ? `${raw} ${meta[field.unit]}`
                    : field.money
                      ? `₹ ${raw}${meta.taxes_included ? ' (inclusive of all taxes)' : ''}`
                      : String(raw)
                  : null;

                return (
                  <div key={field.key} className="grid gap-1 py-3 sm:grid-cols-[1fr_1.4fr] sm:gap-4">
                    <dt className="text-[13px] text-muted">
                      {field.label}
                      <span className="ml-1.5 text-[11px] text-faint">{field.rule}</span>
                    </dt>
                    <dd
                      className={clsx(
                        'text-sm font-medium',
                        value ? 'text-ink' : 'text-bad',
                        field.money && !meta.taxes_included && value && 'text-warn',
                      )}
                    >
                      {value || t('common.notDetected')}
                    </dd>
                  </div>
                );
              })}
            </dl>
          )}

          {tab === 'passed' &&
            (passed.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted">{t('common.none')}</p>
            ) : (
              <ul className="space-y-2.5">
                {passed.map((check, index) => (
                  <li
                    key={`${check.rule_id}-${index}`}
                    className="flex items-start gap-3 rounded border border-ok/20 bg-ok-soft/40 p-3.5"
                  >
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink">{check.rule_name || check.rule_id}</p>
                      <p className="mt-0.5 text-[13px] leading-relaxed text-muted">
                        {check.evidence || check.description}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            ))}

          {tab === 'evidence' && (
            <div className="space-y-5">
              <EvidenceViewer
                evidence={result.evidence || []}
                segments={result.raw_segments || []}
                localFiles={localFiles}
              />
              {(result.raw_text_dump ?? []).length > 0 && (
                <details className="rounded border border-line bg-raised/40">
                  <summary className="cursor-pointer px-4 py-2.5 text-[13px] font-medium text-ink">
                    {t('result.rawText')} ({result.raw_text_dump.length})
                  </summary>
                  <pre className="max-h-72 overflow-auto px-4 pb-4 font-mono text-[12px] leading-relaxed text-muted">
                    {result.raw_text_dump.join('\n')}
                  </pre>
                </details>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      <VerifyPanel
        open={verifying}
        onClose={() => setVerifying(false)}
        result={result}
        onVerified={onResultChange}
      />
    </div>
  );
}
