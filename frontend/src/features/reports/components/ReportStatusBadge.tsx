import { StatusBadge } from "@/components/ui/StatusBadge";
import { REPORT_STATUS_LABEL, type ReportStatus } from "@/types/report";

const VARIANT: Record<ReportStatus, "ok" | "warn" | "error" | "neutral"> = {
  queued: "neutral",
  processing: "warn",
  generated: "ok",
  failed: "error",
};

export function ReportStatusBadge({ status }: { status: ReportStatus }) {
  return <StatusBadge variant={VARIANT[status]}>{REPORT_STATUS_LABEL[status]}</StatusBadge>;
}
