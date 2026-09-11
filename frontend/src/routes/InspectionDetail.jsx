import { ArrowLeft, History } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Card, CardBody, CardHeader, EmptyState, ErrorNote, Skeleton } from '../components/ui';
import { useI18n } from '../context/I18nContext';
import { api } from '../lib/api';
import { formatDateTime } from '../lib/format';
import CasePanel from '../features/scan/CasePanel';
import ResultView from '../features/scan/ResultView';

export default function InspectionDetail() {
  const { id } = useParams();
  const { t } = useI18n();
  const navigate = useNavigate();

  const [inspection, setInspection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    api.inspections
      .get(id)
      .then((data) => !cancelled && setInspection(data))
      .catch((err) => !cancelled && setError(err.status === 404 || err.status === 403 ? t('detail.notFound') : err.message))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [id, t]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-40" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (error || !inspection) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Link to="/repository" className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand hover:underline">
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t('nav.repository')}
        </Link>
        <Card>
          <EmptyState title={error || t('detail.notFound')} />
        </Card>
      </div>
    );
  }

  // The stored report plus the fields the repository row carries, so ResultView
  // renders a saved inspection exactly as it rendered the live scan.
  const result = {
    ...inspection.report,
    inspection_id: inspection.id,
    evidence: inspection.evidence || [],
    status: inspection.status,
    overall_score: inspection.overall_score,
  };

  const trail = inspection.audit_trail || [];

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/repository"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand hover:underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t('nav.repository')}
        </Link>
        <p className="font-mono text-[12px] text-faint">
          {inspection.case_number || inspection.id}
        </p>
      </div>

      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{inspection.product_name}</h1>
        {inspection.brand && <p className="text-sm text-muted">{inspection.brand}</p>}
      </header>

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-[13px] text-muted">
        <span>
          {t('detail.officer')}: <span className="text-ink">{inspection.officer_name || '—'}</span>
        </span>
        <span>
          {t('detail.date')}: <span className="text-ink">{formatDateTime(inspection.created_at)}</span>
        </span>
        {inspection.jurisdiction && (
          <span>
            {t('auth.jurisdiction')}: <span className="text-ink">{inspection.jurisdiction}</span>
          </span>
        )}
      </div>

      <ErrorNote>{error}</ErrorNote>

      <CasePanel inspection={inspection} onUpdated={setInspection} />

      <ResultView
        result={result}
        onResultChange={(revised) => setInspection((prev) => ({ ...prev, report: revised, status: revised.status, overall_score: revised.overall_score }))}
        onReset={() => navigate('/scan')}
      />

      {trail.length > 0 && (
        <Card>
          <CardHeader title={t('detail.auditTrail')} />
          <CardBody className="p-0">
            <ul className="divide-y divide-line">
              {trail.map((entry) => (
                <li key={entry.id} className="flex items-start gap-3 px-5 py-3">
                  <History className="mt-0.5 h-4 w-4 shrink-0 text-faint" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] text-ink">
                      <span className="font-medium">{entry.action.replace(/_/g, ' ').toLowerCase()}</span>
                      {entry.actor_name && <span className="text-muted"> · {entry.actor_name}</span>}
                    </p>
                    {entry.detail && <p className="text-[12px] text-faint">{entry.detail}</p>}
                  </div>
                  <span className="shrink-0 whitespace-nowrap text-[12px] text-faint">
                    {formatDateTime(entry.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
