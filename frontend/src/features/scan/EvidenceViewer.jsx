import clsx from 'clsx';
import { Eye, EyeOff } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '../../components/ui';
import { useI18n } from '../../context/I18nContext';
import { api } from '../../lib/api';

/**
 * Shows a package photograph with the OCR bounding boxes drawn over it.
 *
 * This is what makes a finding checkable: an officer can see exactly where on the
 * pack a declaration was read from, rather than trusting a verdict with no
 * provenance. Boxes are drawn in the original image's pixel space and scaled with
 * a viewBox, so they stay aligned at any display size.
 */
export default function EvidenceViewer({ evidence = [], segments = [], localFiles = null }) {
  const { t } = useI18n();
  const [active, setActive] = useState(0);
  const [showBoxes, setShowBoxes] = useState(true);
  const [urls, setUrls] = useState({});
  const [natural, setNatural] = useState({ width: 0, height: 0 });
  const objectUrls = useRef([]);

  // Stored evidence is behind auth, so it is fetched as a blob rather than
  // pointed at with <img src>, which would send no Authorization header.
  useEffect(() => {
    let cancelled = false;

    if (localFiles?.length) {
      const map = {};
      localFiles.forEach((file, index) => {
        const url = URL.createObjectURL(file);
        objectUrls.current.push(url);
        map[index] = url;
      });
      setUrls(map);
    } else if (evidence.length) {
      Promise.all(
        evidence.map((item) =>
          api.inspections
            .evidenceBlob(item.evidence_id)
            .then((url) => {
              objectUrls.current.push(url);
              return url;
            })
            .catch(() => null),
        ),
      ).then((resolved) => {
        if (cancelled) return;
        const map = {};
        resolved.forEach((url, index) => {
          if (url) map[index] = url;
        });
        setUrls(map);
      });
    }

    return () => {
      cancelled = true;
    };
  }, [evidence, localFiles]);

  // Revoke every object URL once, on unmount.
  useEffect(
    () => () => {
      objectUrls.current.forEach((url) => URL.revokeObjectURL(url));
      objectUrls.current = [];
    },
    [],
  );

  const count = localFiles?.length ?? evidence.length;

  const boxes = useMemo(
    () =>
      segments.filter(
        (segment) =>
          Array.isArray(segment.box) &&
          segment.box.length >= 4 &&
          (segment.image_index ?? 1) === active + 1,
      ),
    [segments, active],
  );

  if (!count) return null;

  const label =
    localFiles?.[active]?.name ?? evidence[active]?.angle ?? `Image ${active + 1}`;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {Array.from({ length: count }).map((_, index) => (
            <button
              key={index}
              onClick={() => setActive(index)}
              className={clsx(
                'rounded px-2.5 py-1 text-[12px] font-medium transition-colors',
                index === active ? 'bg-brand text-brand-ink' : 'bg-raised text-muted hover:text-ink',
              )}
            >
              {localFiles ? `#${index + 1}` : evidence[index]?.angle || `#${index + 1}`}
            </button>
          ))}
        </div>

        {boxes.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            icon={showBoxes ? EyeOff : Eye}
            onClick={() => setShowBoxes((v) => !v)}
          >
            {t('result.showOnImage')} ({boxes.length})
          </Button>
        )}
      </div>

      <div className="relative overflow-hidden rounded-lg border border-line bg-raised">
        {urls[active] ? (
          <>
            <img
              src={urls[active]}
              alt={label}
              className="block h-auto max-h-[60vh] w-full object-contain"
              onLoad={(e) =>
                setNatural({
                  width: e.target.naturalWidth,
                  height: e.target.naturalHeight,
                })
              }
            />
            {showBoxes && natural.width > 0 && boxes.length > 0 && (
              <svg
                className="pointer-events-none absolute inset-0 h-full w-full"
                viewBox={`0 0 ${natural.width} ${natural.height}`}
                preserveAspectRatio="xMidYMid meet"
                aria-hidden
              >
                {boxes.map((segment, index) => {
                  const points = segment.box.map((p) => `${p[0]},${p[1]}`).join(' ');
                  return (
                    <polygon
                      key={index}
                      points={points}
                      fill="rgb(var(--accent) / 0.10)"
                      stroke="rgb(var(--accent))"
                      strokeWidth={Math.max(1.5, natural.width / 600)}
                      vectorEffect="non-scaling-stroke"
                    />
                  );
                })}
              </svg>
            )}
          </>
        ) : (
          <div className="skeleton aspect-[4/3] w-full" />
        )}
      </div>
    </div>
  );
}
