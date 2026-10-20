import { AlertTriangle, Eye, EyeOff, FileWarning } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Badge, Card, CardHeader, Skeleton } from '@/components/ui';
import { cn, humanize } from '@/lib/format';
import { investigationService } from '@/services';
import type { DocumentAnalysis, ImageAnalysis, InvestigationDetail } from '@/types/api';

/** The uploaded file as an object URL, fetched with the session's credentials. */
export function useFileUrl(id: string, enabled: boolean) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!enabled) return undefined;
    let revoked = false;
    let objectUrl: string | null = null;
    investigationService
      .fileBlob(id)
      .then((blob) => {
        if (revoked) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => setError(true));
    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, enabled]);
  return { url, error };
}

function Field({ label, value }: { label: string; value: unknown }) {
  const text = Array.isArray(value) ? value.join(', ') : typeof value === 'number' ? value.toLocaleString() : String(value ?? '—');
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-3 py-1.5 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="break-words font-mono text-xs text-text-primary/90">{text}</dd>
    </div>
  );
}

export function DocumentPanel({ inv, doc }: { inv: InvestigationDetail; doc: DocumentAnalysis }) {
  // A PDF that declares JavaScript or launch actions is not handed to the
  // browser's PDF viewer: its extracted text is shown instead.
  const risky = (doc.active_content?.length ?? 0) > 0;
  const { url } = useFileUrl(inv.id, Boolean(inv.input.has_file) && !risky && !doc.encrypted);

  if (doc.encrypted) {
    return <Card className="p-6 text-sm text-muted">This PDF is password-protected, so its contents were not analysed.</Card>;
  }

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <div className="space-y-6">
        <Card>
          <CardHeader eyebrow="Document" title={humanize(doc.type ?? 'other')} action={<Badge>{doc.pages} page{doc.pages === 1 ? '' : 's'}</Badge>} />
          <dl className="px-5 pb-5 pt-3 sm:px-6 sm:pb-6">
            {Object.entries(doc.fields ?? {}).map(([k, v]) => <Field key={k} label={humanize(k)} value={v} />)}
            {!Object.keys(doc.fields ?? {}).length && <p className="text-sm text-muted">No structured fields were recognised.</p>}
          </dl>
        </Card>
        <Card>
          <CardHeader eyebrow="Structure" title="File forensics" />
          <dl className="px-5 pb-5 pt-3 sm:px-6 sm:pb-6">
            <Field label="Producer" value={doc.metadata?.producer} />
            <Field label="Creator" value={doc.metadata?.creator} />
            <Field label="Created" value={doc.metadata?.created} />
            <Field label="Modified" value={doc.metadata?.modified} />
            <Field label="Incremental saves" value={doc.incremental_saves ?? 0} />
            <Field label="Active content" value={doc.active_content?.length ? doc.active_content : 'none'} />
            <Field label="Scanned pages" value={doc.scanned_pages?.length ? doc.scanned_pages : 'none'} />
            <Field label="OCR" value={doc.ocr?.status === 'done' ? `${doc.ocr.engine} · pages ${doc.ocr.pages?.join(', ')}` : humanize(doc.ocr?.status)} />
          </dl>
          <p className="px-5 pb-5 text-xs text-muted sm:px-6">
            Findings here are potential manipulation indicators. Genuine documents are re-saved and edited too — confirm with the issuer.
          </p>
        </Card>
      </div>

      <Card>
        <CardHeader eyebrow="Preview" title={inv.input.filename ?? 'Document'} />
        <div className="p-5 pt-3 sm:p-6 sm:pt-3">
          {risky ? (
            <div className="space-y-4">
              <p className="flex items-start gap-2 rounded-2xl border border-risk-high/40 bg-risk-high/10 px-4 py-3 text-sm text-text-primary/90">
                <FileWarning className="mt-0.5 h-4 w-4 shrink-0 text-risk-high" aria-hidden />
                This PDF contains active content, so it is not opened in your browser. Extracted text is shown instead.
              </p>
              {doc.page_previews?.map((t, i) => (
                <pre key={i} className="max-h-60 overflow-auto whitespace-pre-wrap rounded-2xl border border-stroke bg-bg p-3 font-mono text-[11px] text-text-primary/85">{t || '(no text)'}</pre>
              ))}
            </div>
          ) : url ? (
            <object data={url} type="application/pdf" className="h-[36rem] w-full rounded-2xl border border-stroke bg-bg" aria-label="PDF preview">
              <p className="p-4 text-sm text-muted">Your browser cannot display PDFs inline.</p>
            </object>
          ) : inv.input.has_file ? (
            <Skeleton className="h-[36rem]" />
          ) : (
            <p className="text-sm text-muted">The original file is only visible to its owner.</p>
          )}
        </div>
      </Card>
    </div>
  );
}

export function ImagePanel({ inv, image }: { inv: InvestigationDetail; image: ImageAnalysis }) {
  const { url } = useFileUrl(inv.id, Boolean(inv.input.has_file));
  const [boxes, setBoxes] = useState(true);
  const words = image.ocr.words ?? [];

  return (
    <div className="grid gap-6 xl:grid-cols-5">
      <Card className="xl:col-span-3">
        <CardHeader
          eyebrow="Image"
          title={`${image.width} × ${image.height} ${image.format}`}
          action={words.length > 0 ? (
            <button onClick={() => setBoxes((v) => !v)} className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted hover:bg-stroke/40 hover:text-text-primary">
              {boxes ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />} OCR boxes
            </button>
          ) : undefined}
        />
        <div className="p-5 pt-3 sm:p-6 sm:pt-3">
          {url ? (
            <div className="relative overflow-hidden rounded-2xl border border-stroke bg-bg">
              <img src={url} alt={inv.input.filename ?? 'Uploaded image'} className="block h-auto w-full" />
              {boxes && words.length > 0 && (
                <svg viewBox={`0 0 ${image.width} ${image.height}`} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
                  {words.map((w, i) => (
                    <rect
                      key={i}
                      x={w.bbox[0]} y={w.bbox[1]} width={w.bbox[2]} height={w.bbox[3]}
                      fill="none"
                      stroke={w.confidence >= 80 ? '#2c7230' : w.confidence >= 50 ? '#9a5c00' : '#b3261e'}
                      strokeWidth={Math.max(1, image.width / 500)}
                    />
                  ))}
                </svg>
              )}
            </div>
          ) : inv.input.has_file ? <Skeleton className="h-80" /> : <p className="text-sm text-muted">The original image is only visible to its owner.</p>}
          {boxes && words.length > 0 && (
            <p className="mt-3 text-[11px] text-muted">Box colour shows OCR confidence per word: green ≥ 80, amber ≥ 50, red below.</p>
          )}
        </div>
      </Card>
      <div className="space-y-6 xl:col-span-2">
        <Card>
          <CardHeader eyebrow="OCR" title={image.ocr.status === 'done' ? `${image.ocr.engine} · ${image.ocr.languages}` : 'Unavailable'}
            action={image.ocr.mean_confidence != null ? <Badge tone={image.ocr.mean_confidence >= 70 ? 'good' : 'warn'}>confidence {image.ocr.mean_confidence}</Badge> : undefined} />
          <div className="p-5 pt-3 sm:p-6 sm:pt-3">
            {image.ocr.status === 'done' ? (
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-2xl border border-stroke bg-bg p-3 font-mono text-[11px] text-text-primary/85">{image.ocr.text || '(no text found)'}</pre>
            ) : (
              <p className="flex items-start gap-2 text-sm text-muted"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{image.ocr.detail}</p>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader eyebrow="Metadata" title="EXIF" />
          <dl className={cn('px-5 pb-5 pt-3 sm:px-6 sm:pb-6')}>
            {Object.keys(image.exif).length ? Object.entries(image.exif).map(([k, v]) => <Field key={k} label={k} value={v} />)
              : <p className="text-sm text-muted">No EXIF metadata (common for screenshots and re-shared images).</p>}
          </dl>
        </Card>
      </div>
    </div>
  );
}
