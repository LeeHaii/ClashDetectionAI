import { Download, FileText, Layers3, LoaderCircle } from "lucide-react";

import { api } from "../api/client";
import type { ClashItem, Report } from "../types";

interface Props {
  report: Report;
  clashes: ClashItem[];
  selectedId?: string;
  batchProgress: { completed: number; total: number } | null;
  onSelect(id: string): void;
  onAnalyzeSelected(): void;
  onAnalyzeAll(): void;
  onDownload(): void;
}

export function ReportPanel({ report, clashes, selectedId, batchProgress, onSelect, onAnalyzeSelected, onAnalyzeAll, onDownload }: Props) {
  const selected = clashes.find((item) => item.id === selectedId);
  return (
    <aside className="hidden w-80 shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-4 xl:block dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center gap-2"><FileText className="text-blue-600" size={20} /><div className="min-w-0"><div className="truncate text-sm font-semibold">{report.title}</div><div className="text-xs text-slate-500">{report.clash_count} clashes · {report.parse_status}</div></div></div>
      <label className="mt-5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Selected clash</label>
      <select aria-label="Selected clash" className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" value={selectedId ?? ""} onChange={(event) => onSelect(event.target.value)}>{clashes.map((clash) => <option key={clash.id} value={clash.id}>{clash.clash_id}</option>)}</select>
      {selected && <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800">{selected.image_path && <img className="h-40 w-full bg-slate-100 object-contain dark:bg-slate-900" src={api.imageUrl(selected.id)} alt={selected.clash_id} />}<dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 p-3 text-xs"><dt className="text-slate-500">Distance</dt><dd>{selected.distance_raw ?? "Unknown"}</dd><dt className="text-slate-500">Grid</dt><dd>{selected.grid ?? "Unknown"}</dd><dt className="text-slate-500">Elements</dt><dd>{selected.elements.map((element) => element.element_id).join(" vs ")}</dd></dl></div>}
      <div className="mt-4 grid gap-2">
        <button className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-40" disabled={!selected || Boolean(batchProgress)} onClick={onAnalyzeSelected}><Layers3 size={16} /> Analyze selected</button>
        <button className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm disabled:opacity-40 dark:border-slate-700" disabled={clashes.length === 0 || Boolean(batchProgress)} onClick={onAnalyzeAll}>{batchProgress ? <LoaderCircle className="animate-spin" size={16} /> : <Layers3 size={16} />} {batchProgress ? `${batchProgress.completed}/${batchProgress.total}` : "Analyze all"}</button>
        <button className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm dark:border-slate-700" onClick={onDownload}><Download size={16} /> Download PDF</button>
      </div>
      {report.errors.length > 0 && <div className="mt-4 rounded-xl bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-100"><strong>{report.errors.length} row warnings</strong><ul className="mt-1 list-disc pl-4">{report.errors.slice(0, 3).map((error) => <li key={`${error.row_index}-${error.message}`}>{error.message}</li>)}</ul></div>}
    </aside>
  );
}
