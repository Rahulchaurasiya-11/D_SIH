import { useEffect, useState } from 'react';

import { Button, Checkbox, ErrorNote, Field, Input, Modal } from '../../components/ui';
import { useI18n } from '../../context/I18nContext';
import { api } from '../../lib/api';
import { useSubmitGuard } from '../../lib/useSubmitGuard';

/**
 * Inspector correction pass.
 *
 * OCR misreads happen — a curved pack, a glare, a faint print. Without a way to
 * correct the reading, one bad frame becomes a wrongful enforcement notice. The
 * corrected values are sent back to the server, which re-runs the same rule engine
 * and marks the inspection as officer-verified.
 */
const FIELDS = [
  { key: 'manufacturer_name', label: 'verify.manufacturer' },
  { key: 'mrp', label: 'verify.mrp', inputMode: 'decimal' },
  { key: 'net_quantity', label: 'verify.netQuantity', inputMode: 'decimal' },
  { key: 'unit_of_measure', label: 'verify.unit', placeholder: 'g / kg / ml / l / N' },
  { key: 'manufacturing_date', label: 'verify.mfgDate', placeholder: 'MM/YYYY' },
  { key: 'consumer_care_email', label: 'verify.email', type: 'email' },
  { key: 'consumer_care_phone', label: 'verify.phone', inputMode: 'tel' },
  { key: 'country_of_origin', label: 'verify.origin', placeholder: 'India' },
];

export default function VerifyPanel({ open, onClose, result, onVerified }) {
  const { t } = useI18n();
  const [values, setValues] = useState({});
  const [taxes, setTaxes] = useState(false);
  const set = (key) => (event) => setValues((prev) => ({ ...prev, [key]: event.target.value }));

  const [runVerify, busy, error, clearError] = useSubmitGuard(async () => {
    // Send only what the officer actually filled in; blank fields must not
    // overwrite a correct reading with an empty string.
    const overrides = { taxes_included: taxes };
    Object.entries(values).forEach(([key, value]) => {
      if (String(value).trim()) overrides[key] = String(value).trim();
    });

    const revised = await api.scan.verify({
      inspection_id: result.inspection_id,
      segments: result.raw_segments || [],
      image_dimensions: result.image_meta
        ? [result.image_meta.height, result.image_meta.width]
        : undefined,
      manual_overrides: overrides,
    });
    onVerified({ ...revised, evidence: result.evidence, inspection_id: result.inspection_id });
    onClose();
  });

  const submit = (event) => {
    event.preventDefault();
    runVerify();
  };

  // Seed from what the engine read, so the officer edits rather than retypes.
  useEffect(() => {
    if (!open) return;
    const meta = result?.extracted_metadata || {};
    const seeded = {};
    FIELDS.forEach((field) => {
      seeded[field.key] = meta[field.key] ?? '';
    });
    setValues(seeded);
    setTaxes(Boolean(meta.taxes_included));
    clearError();
  }, [open, result, clearError]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('verify.title')}
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button form="verify-form" type="submit" loading={busy}>
            {busy ? t('verify.submitting') : t('verify.submit')}
          </Button>
        </div>
      }
    >
      <form id="verify-form" onSubmit={submit} className="space-y-5">
        <p className="rounded border border-line bg-raised px-3.5 py-3 text-[13px] leading-relaxed text-muted">
          {t('verify.help')}
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          {FIELDS.map((field) => (
            <Field key={field.key} label={t(field.label)} htmlFor={`verify-${field.key}`}>
              <Input
                id={`verify-${field.key}`}
                type={field.type || 'text'}
                inputMode={field.inputMode}
                placeholder={field.placeholder}
                value={values[field.key] ?? ''}
                onChange={set(field.key)}
              />
            </Field>
          ))}
        </div>

        <Checkbox
          id="verify-taxes"
          label={t('verify.taxesIncluded')}
          checked={taxes}
          onChange={(e) => setTaxes(e.target.checked)}
        />

        <ErrorNote>{error}</ErrorNote>
      </form>
    </Modal>
  );
}
