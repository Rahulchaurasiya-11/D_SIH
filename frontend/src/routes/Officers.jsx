import { UserCheck, UserX } from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  Badge,
  Button,
  Card,
  CardBody,
  ErrorNote,
  Select,
  Skeleton,
} from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/I18nContext';
import { api } from '../lib/api';
import { formatDate } from '../lib/format';

const ROLES = ['INSPECTOR', 'SENIOR_OFFICER', 'ADMIN'];

export default function Officers() {
  const { t } = useI18n();
  const { user: me } = useAuth();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');

  const load = () => {
    setLoading(true);
    api.auth
      .users()
      .then(setUsers)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const mutate = async (id, action) => {
    setBusyId(id);
    setError('');
    try {
      await action();
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId('');
    }
  };

  if (loading && users.length === 0) {
    return (
      <div className="mx-auto max-w-5xl space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <header>
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{t('users.title')}</h1>
        <p className="mt-1 text-sm text-muted">{t('users.subtitle')}</p>
      </header>

      <ErrorNote onRetry={load} retryLabel={t('common.retry')}>
        {error}
      </ErrorNote>

      <Card>
        <CardBody className="p-0">
          <ul className="divide-y divide-line">
            {users.map((officer) => {
              const isMe = officer.id === me?.id;
              return (
                <li key={officer.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand-soft text-sm font-semibold text-brand">
                    {(officer.full_name || '?').charAt(0).toUpperCase()}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium text-ink">{officer.full_name}</p>
                      {isMe && <Badge tone="brand">You</Badge>}
                      {!officer.is_active && <Badge tone="bad">Inactive</Badge>}
                    </div>
                    <p className="truncate text-[12px] text-faint">
                      {officer.email}
                      {officer.jurisdiction && ` · ${officer.jurisdiction}`}
                      {officer.created_at && ` · ${formatDate(officer.created_at)}`}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <Select
                      value={officer.role}
                      disabled={isMe || busyId === officer.id}
                      onChange={(e) =>
                        mutate(officer.id, () => api.auth.setRole(officer.id, e.target.value))
                      }
                      className="w-44"
                      aria-label={t('users.role')}
                    >
                      {ROLES.map((role) => (
                        <option key={role} value={role}>
                          {t(`role.${role}`)}
                        </option>
                      ))}
                    </Select>

                    <Button
                      variant={officer.is_active ? 'ghost' : 'subtle'}
                      size="sm"
                      icon={officer.is_active ? UserX : UserCheck}
                      disabled={isMe || busyId === officer.id}
                      onClick={() =>
                        mutate(officer.id, () => api.auth.setActive(officer.id, !officer.is_active))
                      }
                    >
                      {t(officer.is_active ? 'users.deactivate' : 'users.activate')}
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        </CardBody>
      </Card>

      <p className="text-[12px] leading-relaxed text-faint">
        Roles are enforced on the server for every request. Hiding a screen in the interface is a
        convenience, not a control — an inspector cannot reach another officer&apos;s inspections even
        by calling the API directly.
      </p>
    </div>
  );
}
