import { FileDropzone } from '@/components/investigation/FileDropzone';
import { InvestigationRow } from '@/components/investigation/InvestigationRow';
import { Card, CardHeader, PageHeader, Skeleton } from '@/components/ui';
import { useInvestigations } from '@/hooks/queries';

const CHECKS: [string, string][] = [
  ['Structure', 'Embedded JavaScript, launch actions and attachments; incremental saves that show the file was edited after it was finished.'],
  ['Metadata', 'Producer and creator tools, creation and modification dates, and whether they are consistent.'],
  ['Content', 'Text per page, with OCR for scanned pages when an OCR engine is installed; document type; invoice fields, GSTIN, PAN and IFSC.'],
  ['Consistency', 'Subtotal plus tax against the total, due date against issue date, future dates, and invoice numbers reused on different documents.'],
];

export default function Documents() {
  const recent = useInvestigations({ type: 'document', page_size: 8 });
  const images = useInvestigations({ type: 'image', page_size: 4 });

  return (
    <>
      <PageHeader
        eyebrow="Document forensics"
        title={<>Is this document <span className="font-display">what it says</span>?</>}
        description="Upload an invoice, statement, certificate or a screenshot. Findings are potential manipulation indicators — reasons to confirm with the issuer, never a verdict of forgery."
      />
      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Card className="p-5 sm:p-6"><FileDropzone /></Card>
          <Card>
            <CardHeader eyebrow="Recent" title="Document investigations" />
            <div className="space-y-2 p-5 pt-4 sm:p-6 sm:pt-4">
              {recent.isLoading ? <Skeleton className="h-32" /> : recent.data?.items.length
                ? recent.data.items.map((inv) => <InvestigationRow key={inv.id} inv={inv} />)
                : <p className="text-sm text-muted">No documents investigated yet.</p>}
              {images.data?.items.map((inv) => <InvestigationRow key={inv.id} inv={inv} />)}
            </div>
          </Card>
        </div>
        <Card>
          <CardHeader eyebrow="Method" title="What is checked" />
          <dl className="space-y-4 p-5 pt-4 sm:p-6 sm:pt-4">
            {CHECKS.map(([t, d]) => (
              <div key={t}><dt className="text-sm text-text-primary">{t}</dt><dd className="mt-1 text-xs leading-relaxed text-muted">{d}</dd></div>
            ))}
            <div>
              <dt className="text-sm text-text-primary">Not yet</dt>
              <dd className="mt-1 text-xs leading-relaxed text-muted">Table extraction and pixel-level image forensics (error-level analysis, copy-move) arrive in Phase 3.</dd>
            </div>
          </dl>
        </Card>
      </div>
    </>
  );
}
