import { AlertTriangle, Check, MapPin, Store } from 'lucide-react';
import { useState } from 'react';

import { Card, CardBody, CardHeader, Field, Input, Select, Textarea } from '../../components/ui';
import { useI18n } from '../../context/I18nContext';

const TYPES = ['RETAIL', 'SUPERMARKET', 'WHOLESALE', 'WAREHOUSE', 'ECOMMERCE', 'OTHER'];

export const EMPTY_PREMISES = {
  premises_name: '',
  premises_address: '',
  premises_type: 'RETAIL',
  premises_licence: '',
  latitude: null,
  longitude: null,
  location_accuracy_m: null,
  remarks: '',
};

/**
 * Captures where the package was found.
 *
 * A notice under the Act is served on a person at a place. A finding that records
 * only "this pack was non-compliant" cannot support one — it does not say whose
 * pack, in whose shop, on what date. The report prints a warning when this is left
 * blank rather than quietly producing an incomplete notice.
 */
export default function PremisesPanel({ value, onChange }) {
  const { t } = useI18n();
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState('');

  const set = (key) => (event) => onChange({ ...value, [key]: event.target.value });

  const captureLocation = () => {
    if (!navigator.geolocation) {
      setLocationError(t('premises.locationUnavailable'));
      return;
    }
    setLocating(true);
    setLocationError('');

    navigator.geolocation.getCurrentPosition(
      (position) => {
        onChange({
          ...value,
          latitude: Number(position.coords.latitude.toFixed(6)),
          longitude: Number(position.coords.longitude.toFixed(6)),
          location_accuracy_m: Math.round(position.coords.accuracy),
        });
        setLocating(false);
      },
      (error) => {
        setLocating(false);
        setLocationError(
          error.code === error.PERMISSION_DENIED
            ? t('premises.locationDenied')
            : t('premises.locationUnavailable'),
        );
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  };

  const hasLocation = value.latitude !== null && value.longitude !== null;

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <Store className="h-4 w-4 text-brand" aria-hidden />
            {t('premises.title')}
          </span>
        }
        subtitle={t('premises.subtitle')}
      />
      <CardBody className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('premises.name')} htmlFor="premises-name">
            <Input
              id="premises-name"
              value={value.premises_name}
              onChange={set('premises_name')}
              placeholder="Sharma General Store"
              autoComplete="off"
            />
          </Field>

          <Field label={t('premises.type')} htmlFor="premises-type">
            <Select id="premises-type" value={value.premises_type} onChange={set('premises_type')}>
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`premises.type${type}`)}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <Field label={t('premises.address')} htmlFor="premises-address">
          <Input
            id="premises-address"
            value={value.premises_address}
            onChange={set('premises_address')}
            placeholder="12 Nehru Market, Karol Bagh, New Delhi - 110005"
            autoComplete="off"
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('premises.licence')} htmlFor="premises-licence">
            <Input
              id="premises-licence"
              value={value.premises_licence}
              onChange={set('premises_licence')}
              placeholder="DL-LM-2026-4417"
              autoComplete="off"
            />
          </Field>

          <Field label=" ">
            <button
              type="button"
              onClick={captureLocation}
              disabled={locating}
              className={
                'flex h-10 w-full items-center justify-center gap-2 rounded border px-3 text-sm ' +
                'font-medium transition-colors disabled:opacity-60 ' +
                (hasLocation
                  ? 'border-ok/30 bg-ok-soft text-ok'
                  : 'border-line bg-surface text-muted hover:border-brand/40 hover:text-ink')
              }
            >
              {hasLocation ? (
                <>
                  <Check className="h-4 w-4 shrink-0" aria-hidden />
                  {t('premises.located', { accuracy: value.location_accuracy_m ?? '?' })}
                </>
              ) : (
                <>
                  <MapPin className="h-4 w-4 shrink-0" aria-hidden />
                  {locating ? t('premises.locating') : t('premises.useLocation')}
                </>
              )}
            </button>
          </Field>
        </div>

        {locationError && <p className="text-[12px] text-warn">{locationError}</p>}

        <Field label={t('premises.remarks')} htmlFor="premises-remarks">
          <Textarea
            id="premises-remarks"
            value={value.remarks}
            onChange={set('remarks')}
            rows={2}
            placeholder="Pack taken from the front shelf."
            className="min-h-0"
          />
        </Field>

        {!value.premises_name.trim() && (
          <p className="flex items-start gap-2 rounded border border-warn/25 bg-warn-soft px-3.5 py-2.5 text-[12px] leading-relaxed text-warn">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            {t('premises.missingWarning')}
          </p>
        )}
      </CardBody>
    </Card>
  );
}
