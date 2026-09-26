export type RecordSummary = { id: string; status: string };

export function summarize(record: RecordSummary): string {
  return `${record.id}:${record.status}`;
}
