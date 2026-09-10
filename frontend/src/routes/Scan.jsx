import clsx from 'clsx';
import { Globe, Keyboard, Play, ScanLine } from 'lucide-react';
import { useMemo, useState } from 'react';

import {
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Field,
  Input,
  Select,
  Textarea,
} from '../components/ui';
import { useI18n } from '../context/I18nContext';
import { api } from '../lib/api';
import { readImages } from '../lib/browserOcr';
import CaptureSlots, { ANGLES } from '../features/scan/CaptureSlots';
import PremisesPanel, { EMPTY_PREMISES } from '../features/scan/PremisesPanel';
import ResultView from '../features/scan/ResultView';

const OCR_LANGUAGES = [
  ['auto', 'scan.languageAuto'],
  ['en', 'English'],
  ['hi', 'हिन्दी'],
  ['mr', 'मराठी'],
  ['bn', 'বাংলা'],
  ['te', 'తెలుగు'],
  ['ta', 'தமிழ்'],
];

/** Shows an abbreviated label below `sm`, where the full one overflows a 375px row. */
function Tab({ active, onClick, icon: Icon, label, shortLabel }) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'flex flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded px-2 py-2.5',
        'text-[13px] font-medium transition-colors sm:flex-none sm:gap-2 sm:px-4',
        active ? 'bg-brand text-brand-ink shadow-card' : 'text-muted hover:bg-raised hover:text-ink',
      )}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden />
      <span className="sm:hidden">{shortLabel}</span>
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

export default function Scan() {
  const { t } = useI18n();

  const [mode, setMode] = useState('images');
  const [files, setFiles] = useState({});
  const [engine, setEngine] = useState('rapidocr');
  const [ocrLang, setOcrLang] = useState('auto');

  const [premises, setPremises] = useState(EMPTY_PREMISES);
  const [labelText, setLabelText] = useState('');
  const [listing, setListing] = useState({
    listing_text: '', listing_html: '', source_url: '', platform: '', product_title: '',
  });

  const [result, setResult] = useState(null);
  const [localFiles, setLocalFiles] = useState(null);
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const orderedFiles = useMemo(
    () => ANGLES.map((angle) => files[angle.id]).filter(Boolean),
    [files],
  );

  const canRun =
    mode === 'images'
      ? orderedFiles.length > 0
      : mode === 'text'
        ? labelText.trim().length > 0
        : listing.listing_text.trim().length > 0 || listing.listing_html.trim().length > 0;

  const reset = () => {
    setResult(null);
    setLocalFiles(null);
    setFiles({});
    setPremises(EMPTY_PREMISES);
    setLabelText('');
    setListing({ listing_text: '', listing_html: '', source_url: '', platform: '', product_title: '' });
    setError('');
    setNotice('');
    setProgress(0);
  };

  const run = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    setProgress(0);

    try {
      if (mode === 'text') {
        setStatusText(t('scan.analysing'));
        setResult(await api.scan.text({ raw_text: labelText, filename: 'Typed label', source: 'manual' }));
        setLocalFiles(null);
      } else if (mode === 'listing') {
        setStatusText(t('scan.analysing'));
        setResult(await api.scan.listing(listing));
        setLocalFiles(null);
      } else {
        setStatusText(t('scan.analysing'));
        try {
          const response = await api.scan.images(orderedFiles, {
            ocrLang, aiEngine: engine, context: premises,
          });
          setResult(response);
          setLocalFiles(orderedFiles);
        } catch (serverError) {
          // The server is unreachable or has no OCR engine installed. Read the text
          // here instead, then still let the SERVER decide compliance - the browser
          // never rules on the law.
          if (serverError.status && serverError.status !== 0 && serverError.status < 500) throw serverError;

          setStatusText(t('scan.browserOcr'));
          const { text, segments, dimensions } = await readImages(orderedFiles, setProgress);
          if (!text.trim()) throw serverError;

          const response = await api.scan.text({
            raw_text: text,
            segments: segments.length ? segments : undefined,
            image_dimensions: dimensions,
            filename: orderedFiles[0]?.name || 'package.jpg',
            source: 'browser-ocr',
          });
          setResult(response);
          setLocalFiles(orderedFiles);
          setNotice(t('scan.browserOcrNote'));
        }
      }
    } catch (err) {
      setError(err.message || t('common.error'));
    } finally {
      setBusy(false);
      setStatusText('');
      setProgress(0);
    }
  };

  if (result) {
    return (
      <div className="mx-auto max-w-4xl">
        {notice && (
          <p className="mb-4 rounded border border-warn/25 bg-warn-soft px-3.5 py-3 text-[13px] text-warn">
            {notice}
          </p>
        )}
        <ResultView
          result={result}
          localFiles={localFiles}
          onResultChange={setResult}
          onReset={reset}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{t('scan.title')}</h1>
        <p className="mt-1 text-sm text-muted">{t('scan.subtitle')}</p>
      </header>

      <div className="flex gap-1 rounded-lg border border-line bg-surface p-1">
        <Tab
          active={mode === 'images'} onClick={() => setMode('images')} icon={ScanLine}
          label={t('scan.tabImages')} shortLabel={t('scan.tabImagesShort')}
        />
        <Tab
          active={mode === 'text'} onClick={() => setMode('text')} icon={Keyboard}
          label={t('scan.tabText')} shortLabel={t('scan.tabTextShort')}
        />
        <Tab
          active={mode === 'listing'} onClick={() => setMode('listing')} icon={Globe}
          label={t('scan.tabListing')} shortLabel={t('scan.tabListingShort')}
        />
      </div>

      <Card>
        {mode === 'images' && (
          <>
            <CardHeader title={t('scan.tabImages')} subtitle={t('scan.frontRequired')} />
            <CardBody className="space-y-5">
              <CaptureSlots files={files} onChange={setFiles} />

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t('scan.engine')} htmlFor="engine">
                  <Select id="engine" value={engine} onChange={(e) => setEngine(e.target.value)}>
                    <option value="rapidocr">{t('scan.engineOcr')}</option>
                    <option value="vlm">{t('scan.engineVlm')}</option>
                  </Select>
                </Field>
                <Field label={t('scan.language')} htmlFor="ocrLang">
                  <Select id="ocrLang" value={ocrLang} onChange={(e) => setOcrLang(e.target.value)}>
                    {OCR_LANGUAGES.map(([code, label]) => (
                      <option key={code} value={code}>
                        {code === 'auto' ? t(label) : label}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            </CardBody>
          </>
        )}

        {mode === 'text' && (
          <>
            <CardHeader title={t('scan.tabText')} subtitle={t('scan.textHelp')} />
            <CardBody>
              <Textarea
                value={labelText}
                onChange={(e) => setLabelText(e.target.value)}
                placeholder={t('scan.textPlaceholder')}
                rows={12}
                className="font-mono text-[13px]"
              />
            </CardBody>
          </>
        )}

        {mode === 'listing' && (
          <>
            <CardHeader title={t('scan.tabListing')} subtitle={t('scan.listingHelp')} />
            <CardBody className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t('scan.listingProduct')} htmlFor="listing-title">
                  <Input
                    id="listing-title"
                    value={listing.product_title}
                    onChange={(e) => setListing({ ...listing, product_title: e.target.value })}
                    placeholder="Roasted almonds 500 g"
                  />
                </Field>
                <Field label={t('scan.listingPlatform')} htmlFor="listing-platform">
                  <Input
                    id="listing-platform"
                    value={listing.platform}
                    onChange={(e) => setListing({ ...listing, platform: e.target.value })}
                    placeholder="Marketplace name"
                  />
                </Field>
              </div>

              <Field label={t('scan.listingUrl')} htmlFor="listing-url">
                <Input
                  id="listing-url"
                  type="url"
                  value={listing.source_url}
                  onChange={(e) => setListing({ ...listing, source_url: e.target.value })}
                  placeholder="https://…"
                />
              </Field>

              <Field label={t('scan.listingText')} htmlFor="listing-text">
                <Textarea
                  id="listing-text"
                  value={listing.listing_text}
                  onChange={(e) => setListing({ ...listing, listing_text: e.target.value })}
                  placeholder={t('scan.textPlaceholder')}
                  rows={9}
                  className="font-mono text-[13px]"
                />
              </Field>

              <details className="rounded border border-line bg-raised/40">
                <summary className="cursor-pointer px-3.5 py-2.5 text-[13px] font-medium text-ink">
                  {t('scan.listingHtml')}
                </summary>
                <div className="px-3.5 pb-3.5">
                  <Textarea
                    value={listing.listing_html}
                    onChange={(e) => setListing({ ...listing, listing_html: e.target.value })}
                    rows={6}
                    className="font-mono text-[12px]"
                    placeholder="<div>…</div>"
                  />
                </div>
              </details>
            </CardBody>
          </>
        )}
      </Card>

      {mode !== 'text' && <PremisesPanel value={premises} onChange={setPremises} />}

      <ErrorNote>{error}</ErrorNote>

      {busy && progress > 0 && (
        <div className="space-y-1.5">
          <p className="text-[13px] text-muted">{statusText}</p>
          <div className="h-1.5 overflow-hidden rounded-full bg-raised">
            <div
              className="h-full rounded-full bg-brand transition-[width] duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* On a phone this is a real action bar pinned above the tab bar, not a
          translucent button floating over the capture slots. */}
      <div
        className="sticky bottom-[3.75rem] z-20 -mx-4 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur-md
                   sm:-mx-6 sm:px-6
                   lg:static lg:m-0 lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none"
      >
        <Button
          size="lg"
          icon={Play}
          onClick={run}
          loading={busy}
          disabled={!canRun}
          className="w-full shadow-lift"
        >
          {busy ? statusText || t('scan.analysing') : t('scan.analyse')}
        </Button>
      </div>
    </div>
  );
}
