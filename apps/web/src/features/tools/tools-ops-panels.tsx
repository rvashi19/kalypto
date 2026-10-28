import type { ComplianceCoverageResponse } from "@repo/shared";
import { Alert, Badge, Button, EmptyState, Textarea } from "@repo/ui";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { api } from "../../lib/api";
import { Metric, PanelFrame } from "./tools-shared";
import { formatMoney } from "./tools-utils";

export function ShipmentActionPanel({
  title,
  description,
  emptyText,
  shipments,
  actionLabel,
  badge,
  footer,
}: {
  title: string;
  description: string;
  emptyText: string;
  shipments: Array<{
    id: string;
    product_name: string;
    hsn_code: string;
    destination_country: string;
  }>;
  actionLabel: string;
  badge?: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <PanelFrame title={title} description={description} badge={badge}>
      {!shipments.length ? (
        <EmptyState title="Nothing to show yet" description={emptyText} action={footer} />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {shipments.map((shipment) => (
            <Link
              key={shipment.id}
              to={`/shipments/${shipment.id}`}
              className="rounded-card border border-line bg-surface p-4 transition-colors hover:border-brand hover:bg-brand-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
            >
              <p className="font-semibold text-ink">{shipment.product_name}</p>
              <p className="mt-1 text-xs text-ink-2">
                HSN <span className="font-mono">{shipment.hsn_code}</span> /{" "}
                {shipment.destination_country}
              </p>
              <p className="mt-4 text-sm font-semibold text-brand">{actionLabel} - open</p>
            </Link>
          ))}
        </div>
      )}
      {shipments.length && footer ? <div className="mt-4">{footer}</div> : null}
    </PanelFrame>
  );
}

export function ClaimsPanel({
  shipments,
  discrepancies,
}: {
  shipments: Array<{
    id: string;
    product_name: string;
    destination_country: string;
    fob_value: number | null;
    invoice_currency: string;
  }>;
  discrepancies: Awaited<ReturnType<typeof api.discrepancyDashboard>> | undefined;
}) {
  return (
    <PanelFrame
      title="Shipment & Claims Tracker"
      description="A practical view of what needs attention before claims or refunds get locked."
    >
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Findings" value={String(discrepancies?.total ?? 0)} />
        <Metric label="Critical" value={String(discrepancies?.critical ?? 0)} />
        <Metric label="Lock risk" value={String(discrepancies?.lock_risk ?? 0)} />
        <Metric label="Money at risk" value={formatMoney(discrepancies?.potential_amount ?? 0)} />
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-card border border-line bg-surface p-4">
          <h3 className="text-sm font-semibold text-ink">Recent shipments</h3>
          <div className="mt-3 space-y-2">
            {shipments.length ? (
              shipments.map((shipment) => (
                <Link
                  key={shipment.id}
                  to={`/shipments/${shipment.id}`}
                  className="flex items-center justify-between rounded-panel border border-line px-3 py-2 hover:border-brand"
                >
                  <span>
                    <span className="block text-sm text-ink">{shipment.product_name}</span>
                    <span className="text-xs text-ink-2">{shipment.destination_country}</span>
                  </span>
                  <span className="text-xs text-ink-2">
                    {formatMoney(shipment.fob_value, shipment.invoice_currency)}
                  </span>
                </Link>
              ))
            ) : (
              <p className="text-sm text-ink-2">No shipments yet.</p>
            )}
          </div>
        </div>
        <div className="rounded-card border border-line bg-surface p-4">
          <h3 className="text-sm font-semibold text-ink">Latest findings</h3>
          <div className="mt-3 space-y-2">
            {discrepancies?.items.length ? (
              discrepancies.items.slice(0, 5).map((item) => (
                <Link
                  key={item.id}
                  to={`/shipments/${item.shipment_id}`}
                  className="block rounded-panel border border-line px-3 py-2 hover:border-brand"
                >
                  <span className="block text-sm text-ink">{item.message}</span>
                  <span className="mt-1 block text-xs capitalize text-ink-2">
                    {item.severity} / {item.type.replaceAll("_", " ")}
                  </span>
                </Link>
              ))
            ) : (
              <p className="text-sm text-ink-2">
                No persisted findings yet. Run reconciliation on a shipment.
              </p>
            )}
          </div>
        </div>
      </div>
    </PanelFrame>
  );
}

export function AlertsPanel({
  dueSources,
  sourceChanges,
  coverage,
  selectedChangeId,
  selectedChangeDetail,
  evidenceJson,
  discrepancyTotal,
  critical,
  lockRisk,
  isScraping,
  isReviewing,
  isIngesting,
  ingestResult,
  ingestError,
  onScrape,
  onSelectChange,
  onReview,
  onEvidenceJsonChange,
  onIngestEvidence,
}: {
  dueSources: Array<{
    source_url: string;
    country: string;
    category: string;
    last_checked_at: string | null;
  }>;
  sourceChanges: Array<{
    id: string;
    source_url: string;
    country: string;
    category: string;
    created_at: string;
  }>;
  coverage: ComplianceCoverageResponse | undefined;
  selectedChangeId: string | null;
  selectedChangeDetail: Awaited<ReturnType<typeof api.sourceChangeDetail>> | undefined;
  evidenceJson: string;
  discrepancyTotal: number;
  critical: number;
  lockRisk: number;
  isScraping: boolean;
  isReviewing: boolean;
  isIngesting: boolean;
  ingestResult: Awaited<ReturnType<typeof api.ingestComplianceRecords>> | undefined;
  ingestError: unknown;
  onScrape: (source: { source_url: string; country: string; category: string }) => void;
  onSelectChange: (changeId: string | null) => void;
  onReview: (changeId: string, status: "reviewed" | "ignored") => void;
  onEvidenceJsonChange: (value: string) => void;
  onIngestEvidence: () => void;
}) {
  const coverageCells = coverage?.cells ?? [];
  const statusStyles = {
    verified: "border-success-border bg-success-bg text-success-fg",
    partial: "border-info-border bg-info-bg text-info-fg",
    needs_review: "border-warning-border bg-warning-bg text-warning-fg",
    empty: "border-line-strong bg-surface text-ink-2",
  } as const;

  return (
    <PanelFrame
      title="Compliance Alerts"
      description="Operational alerts for stale sources, source changes, and claim-risk findings."
    >
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label="Total findings" value={String(discrepancyTotal)} />
        <Metric label="Critical findings" value={String(critical)} />
        <Metric label="Lock-risk findings" value={String(lockRisk)} />
      </div>
      {coverage ? (
        <div className="mt-5 rounded-card border border-line bg-surface p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-ink">Compliance coverage matrix</h3>
              <p className="mt-1 text-xs text-ink-2">
                Refresh interval: every {coverage.refresh_interval_days} days / due sources:{" "}
                {coverage.due_sources_count} / changes needing review:{" "}
                {coverage.source_changes_needing_review}
              </p>
            </div>
            <Badge tone="info">Review-first data</Badge>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {coverageCells.map((cell) => (
              <div
                key={`${cell.country}-${cell.category}`}
                className={`rounded-panel border p-3 ${statusStyles[cell.status]}`}
              >
                <p className="text-xs font-medium">{cell.status.replaceAll("_", " ")}</p>
                <p className="mt-1 text-sm font-semibold text-ink">
                  {cell.country} / {cell.category}
                </p>
                <p className="mt-1 text-xs">
                  {cell.approved_fresh_records} fresh / {cell.pending_or_draft_records} pending /{" "}
                  {cell.stale_records} stale / {cell.official_sources} official source(s)
                </p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-ink-3">{coverage.disclaimer}</p>
        </div>
      ) : null}
      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <div className="rounded-card border border-line bg-surface p-4">
          <h3 className="text-sm font-semibold text-ink">Source refresh queue</h3>
          <div className="mt-3 space-y-2">
            {dueSources.length ? (
              dueSources.slice(0, 6).map((source) => (
                <div
                  key={`${source.source_url}-${source.country}`}
                  className="rounded-panel border border-line p-3"
                >
                  <p className="truncate text-sm text-ink">{source.source_url}</p>
                  <p className="mt-1 text-xs text-ink-2">
                    {source.country} / {source.category} / checked{" "}
                    {source.last_checked_at ?? "never"}
                  </p>
                  <Button
                    className="mt-2"
                    size="sm"
                    variant="secondary"
                    loading={isScraping}
                    onClick={() => onScrape(source)}
                  >
                    Refresh source
                  </Button>
                </div>
              ))
            ) : (
              <p className="text-sm text-ink-2">No sources are due right now.</p>
            )}
          </div>
        </div>
        <div className="rounded-card border border-line bg-surface p-4">
          <h3 className="text-sm font-semibold text-ink">Change review queue</h3>
          <div className="mt-3 space-y-2">
            {sourceChanges.length ? (
              sourceChanges.slice(0, 6).map((change) => (
                <div
                  key={change.id}
                  className="rounded-panel border border-info-border bg-info-bg p-3"
                >
                  <p className="truncate text-sm text-ink">{change.source_url}</p>
                  <p className="mt-1 text-xs text-ink-2">
                    {change.country} / {change.category} /{" "}
                    {new Date(change.created_at).toLocaleString()}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() =>
                        onSelectChange(selectedChangeId === change.id ? null : change.id)
                      }
                    >
                      {selectedChangeId === change.id ? "Hide evidence" : "View evidence"}
                    </Button>
                    <Button
                      size="sm"
                      loading={isReviewing}
                      onClick={() => onReview(change.id, "reviewed")}
                    >
                      Mark reviewed
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={isReviewing}
                      onClick={() => onReview(change.id, "ignored")}
                    >
                      Ignore change
                    </Button>
                  </div>
                  {selectedChangeId === change.id && selectedChangeDetail ? (
                    <div className="mt-3 grid gap-3 text-xs">
                      <div className="rounded-panel border border-line bg-surface p-3">
                        <p className="font-semibold text-ink">
                          Current snapshot: {selectedChangeDetail.current_title}
                        </p>
                        <p className="mt-1 text-ink-2">
                          Scraped{" "}
                          {new Date(selectedChangeDetail.current_scraped_at).toLocaleString()}
                        </p>
                        <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-panel bg-surface-2 p-3 text-ink">
                          {selectedChangeDetail.current_markdown_excerpt}
                        </pre>
                      </div>
                      {selectedChangeDetail.previous_markdown_excerpt ? (
                        <div className="rounded-panel border border-line bg-surface p-3">
                          <p className="font-semibold text-ink">
                            Previous snapshot: {selectedChangeDetail.previous_title ?? "Untitled"}
                          </p>
                          <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-panel bg-surface-2 p-3 text-ink-2">
                            {selectedChangeDetail.previous_markdown_excerpt}
                          </pre>
                        </div>
                      ) : null}
                      <p className="text-ink-2">{selectedChangeDetail.excerpt_notice}</p>
                    </div>
                  ) : null}
                </div>
              ))
            ) : (
              <p className="text-sm text-ink-2">No scraped changes need review.</p>
            )}
          </div>
        </div>
      </div>
      <div className="mt-5 rounded-card border border-line bg-surface p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-ink">Reviewed evidence ingest</h3>
            <p className="mt-1 max-w-2xl text-xs text-ink-2">
              Paste reviewed compliance requirement JSON after checking the official source. Use
              `review_status: "approved"` only when a human operator has verified the wording.
            </p>
          </div>
          <Button
            size="sm"
            loading={isIngesting}
            disabled={!evidenceJson.trim()}
            onClick={onIngestEvidence}
          >
            {isIngesting ? "Ingesting..." : "Ingest evidence"}
          </Button>
        </div>
        <Textarea
          className="mt-4 min-h-48 font-mono"
          aria-label="Reviewed compliance requirement JSON"
          value={evidenceJson}
          onChange={(event) => onEvidenceJsonChange(event.target.value)}
          placeholder={`[
  {
    "country": "USA",
    "category": "spices",
    "hsn_code": "0904",
    "product_keywords": ["chilli", "spice"],
    "requirement_type": "labeling",
    "requirement_text": "Operator-reviewed requirement text from the official source.",
    "source_url": "https://official-source.example/page",
    "source_name": "Official authority page",
    "source_authority_level": "official",
    "confidence_score": 80,
    "review_status": "approved",
    "reviewed_by": "operator@example.com"
  }
]`}
        />
        {ingestResult ? (
          <Alert tone="success" className="mt-3">
            Ingested {ingestResult.total} record(s): {ingestResult.created} created,{" "}
            {ingestResult.updated} updated.
          </Alert>
        ) : null}
        {ingestError instanceof Error ? (
          <Alert tone="danger" title="Could not ingest evidence" className="mt-3">
            {ingestError.message}
          </Alert>
        ) : null}
      </div>
    </PanelFrame>
  );
}
