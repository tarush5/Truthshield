import { FileUp, Loader2 } from 'lucide-react';
import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { ErrorNotice } from '@/components/ui';
import { useUploadInvestigation } from '@/hooks/queries';
import { cn } from '@/lib/format';

const ACCEPT: Record<string, string> = {
  pdf: 'application/pdf',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  webp: 'image/webp',
};
const MAX_MB = 25;

/** Client-side check only, for a fast message; the server sniffs the bytes regardless. */
export function checkFile(file: File, accept: string[] = Object.keys(ACCEPT)): string | null {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!accept.includes(ext)) return `Unsupported file type. Use ${accept.map((a) => a.toUpperCase()).join(', ')}.`;
  if (file.size === 0) return 'The file is empty.';
  if (file.size > MAX_MB * 1024 * 1024) return `The file is larger than ${MAX_MB} MB.`;
  return null;
}

export function FileDropzone({ accept = Object.keys(ACCEPT), hint }: { accept?: string[]; hint?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const upload = useUploadInvestigation();
  const navigate = useNavigate();

  const handle = async (file: File | undefined) => {
    if (!file) return;
    const problem = checkFile(file, accept);
    setLocalError(problem);
    if (problem) return;
    const created = await upload.mutateAsync(file);
    navigate(`/app/investigations/${created.id}`);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handle(e.dataTransfer.files?.[0]).catch(() => undefined);
  };

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      input.current?.click();
    }
  };

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload a file to investigate"
        onClick={() => input.current?.click()}
        onKeyDown={onKey}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'relative flex cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed px-6 py-12 text-center transition-colors',
          dragging ? 'border-accent bg-accent/10' : 'border-stroke hover:border-muted/60 hover:bg-stroke/20',
        )}
      >
        {upload.isPending ? (
          <Loader2 className="h-8 w-8 animate-spin text-accent" aria-hidden />
        ) : (
          <FileUp className="h-8 w-8 text-muted" aria-hidden />
        )}
        <p className="mt-4 font-display text-2xl text-text-primary">
          {upload.isPending ? 'Uploading…' : 'Drop a file, or click to choose'}
        </p>
        <p className="mt-2 max-w-sm text-xs text-muted">
          {hint ?? `${accept.map((a) => a.toUpperCase()).join(', ')} up to ${MAX_MB} MB. The contents are checked against the extension, hashed, and parsed — never executed.`}
        </p>
        <input
          ref={input}
          type="file"
          className="sr-only"
          accept={accept.map((a) => `.${a},${ACCEPT[a]}`).join(',')}
          onChange={(e) => handle(e.target.files?.[0]).catch(() => undefined)}
          tabIndex={-1}
        />
      </div>
      {localError && <ErrorNotice error={new Error(localError)} className="mt-4" />}
      {upload.error && <ErrorNotice error={upload.error} className="mt-4" />}
    </div>
  );
}
