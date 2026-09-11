import clsx from 'clsx';
import { Camera, Image as ImageIcon, RefreshCw, Upload, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Button, Modal } from '../../components/ui';
import { useI18n } from '../../context/I18nContext';

/**
 * The four angles the rule engine reasons about. Front alone is enough to run a
 * check; the others raise recall because declarations are usually on the back.
 */
export const ANGLES = [
  { id: 1, key: 'scan.angleFront', required: true },
  { id: 2, key: 'scan.angleBack' },
  { id: 3, key: 'scan.angleSide' },
  { id: 4, key: 'scan.angleTop' },
];

/* --------------------------------------------------------------------------- */
/* Camera                                                                       */
/* --------------------------------------------------------------------------- */

function CameraModal({ open, onClose, onCapture, angleLabel }) {
  const { t } = useI18n();
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [facing, setFacing] = useState('environment');
  const [error, setError] = useState('');

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    if (!open) {
      stop();
      return undefined;
    }

    let cancelled = false;
    setError('');

    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: facing, width: { ideal: 1920 } }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err?.name === 'NotAllowedError'
              ? 'Camera permission was denied. Allow it in your browser settings, or upload a photo instead.'
              : 'No camera available on this device. Upload a photo instead.',
          );
        }
      });

    return () => {
      cancelled = true;
      stop();
    };
  }, [open, facing, stop]);

  const capture = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        onCapture(new File([blob], `capture_${Date.now()}.jpg`, { type: 'image/jpeg' }));
        onClose();
      },
      'image/jpeg',
      0.92,
    );
  };

  return (
    <Modal open={open} onClose={onClose} title={`${t('scan.camera')} — ${angleLabel}`} size="lg">
      {error ? (
        <p className="rounded border border-bad/25 bg-bad-soft px-4 py-3 text-sm text-bad">{error}</p>
      ) : (
        <div className="space-y-4">
          <div className="relative overflow-hidden rounded-lg bg-ink">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="h-auto max-h-[60vh] w-full object-contain"
            />
            {/* Framing guide: keeps the declaration panel inside the frame. */}
            <div className="pointer-events-none absolute inset-6 rounded border-2 border-dashed border-white/40" />
          </div>

          <div className="flex items-center justify-between gap-3">
            <Button
              variant="secondary"
              icon={RefreshCw}
              onClick={() => setFacing((f) => (f === 'environment' ? 'user' : 'environment'))}
            >
              Flip
            </Button>
            <Button size="lg" icon={Camera} onClick={capture}>
              Capture
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

/* --------------------------------------------------------------------------- */
/* Slots                                                                        */
/* --------------------------------------------------------------------------- */

function Slot({ angle, file, onPick, onCamera, onRemove }) {
  const { t } = useI18n();
  const inputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped?.type.startsWith('image/')) onPick(dropped);
  };

  const label = t(angle.key);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={clsx(
        'group relative aspect-[4/5] overflow-hidden rounded-lg border-2 border-dashed transition-colors',
        dragging ? 'border-brand bg-brand-soft' : file ? 'border-solid border-line' : 'border-line bg-raised/40',
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={(e) => {
          const picked = e.target.files?.[0];
          if (picked) onPick(picked);
          e.target.value = '';
        }}
      />

      {preview ? (
        <>
          <img src={preview} alt={label} className="h-full w-full object-cover" />
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink/80 to-transparent px-2.5 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-white">{label}</p>
          </div>
          <button
            onClick={onRemove}
            className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-full bg-ink/70 text-white transition-colors hover:bg-bad"
            aria-label={`${t('scan.remove')} ${label}`}
          >
            <X className="h-3.5 w-3.5" aria-hidden />
          </button>
        </>
      ) : (
        <div className="flex h-full flex-col items-center justify-center gap-2 p-3 text-center">
          <ImageIcon className="h-6 w-6 text-faint" aria-hidden />
          <p className="text-[12px] font-medium text-ink">
            {label}
            {angle.required && <span className="ml-1 text-bad">*</span>}
          </p>
          <div className="mt-1 flex gap-1.5">
            <button
              onClick={() => inputRef.current?.click()}
              className="rounded bg-surface px-2 py-1 text-[11px] font-medium text-muted shadow-card transition-colors hover:text-brand"
            >
              <Upload className="mr-1 inline h-3 w-3" aria-hidden />
              {t('scan.upload')}
            </button>
            <button
              onClick={onCamera}
              className="rounded bg-surface px-2 py-1 text-[11px] font-medium text-muted shadow-card transition-colors hover:text-brand"
            >
              <Camera className="mr-1 inline h-3 w-3" aria-hidden />
              {t('scan.camera')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CaptureSlots({ files, onChange }) {
  const { t } = useI18n();
  const [cameraFor, setCameraFor] = useState(null);

  const setSlot = (angleId, file) => {
    const next = { ...files };
    if (file) next[angleId] = file;
    else delete next[angleId];
    onChange(next);
  };

  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {ANGLES.map((angle) => (
          <Slot
            key={angle.id}
            angle={angle}
            file={files[angle.id]}
            onPick={(file) => setSlot(angle.id, file)}
            onCamera={() => setCameraFor(angle)}
            onRemove={() => setSlot(angle.id, null)}
          />
        ))}
      </div>

      <CameraModal
        open={Boolean(cameraFor)}
        angleLabel={cameraFor ? t(cameraFor.key) : ''}
        onClose={() => setCameraFor(null)}
        onCapture={(file) => setSlot(cameraFor.id, file)}
      />
    </>
  );
}
