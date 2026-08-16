import { Paperclip, Send, Square, X } from "lucide-react";
import { DragEvent, KeyboardEvent, useRef, useState } from "react";

interface Props {
  busy: boolean;
  uploadProgress: number | null;
  onSend(text: string, files: File[]): Promise<void>;
  onStop(): void;
}

const accepted = ".html,.htm,.zip,.jpg,.jpeg,.png";

export function Composer({ busy, uploadProgress, onSend, onStop }: Props) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const submit = async () => {
    if (busy || (!text.trim() && files.length === 0)) return;
    const value = text.trim() || "Analyze the attached clash.";
    setText("");
    setFiles([]);
    await onSend(value, files);
  };
  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  };
  const drop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    setFiles((current) => [...current, ...Array.from(event.dataTransfer.files)].slice(0, 20));
  };

  return (
    <div className="mx-auto w-full max-w-4xl px-3 pb-4">
      <div className={`rounded-2xl border bg-white p-2 shadow-lg transition dark:bg-slate-900 ${dragging ? "border-blue-500 ring-2 ring-blue-200" : "border-slate-200 dark:border-slate-700"}`} onDragEnter={() => setDragging(true)} onDragLeave={() => setDragging(false)} onDragOver={(event) => event.preventDefault()} onDrop={drop}>
        {files.length > 0 && <div className="flex flex-wrap gap-2 p-2">{files.map((file, index) => <span key={`${file.name}-${index}`} className="flex items-center gap-1 rounded-lg bg-blue-50 px-2 py-1 text-xs text-blue-900 dark:bg-blue-950 dark:text-blue-100">{file.name}<button aria-label={`Remove ${file.name}`} onClick={() => setFiles((current) => current.filter((_, itemIndex) => index !== itemIndex))}><X size={13} /></button></span>)}</div>}
        {uploadProgress !== null && <div className="mx-2 h-1 overflow-hidden rounded bg-slate-200"><div className="h-full bg-blue-600 transition-all" style={{ width: `${uploadProgress}%` }} /></div>}
        <div className="flex items-end gap-2">
          <input ref={input} className="hidden" type="file" accept={accepted} multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} />
          <button aria-label="Attach files" className="rounded-xl p-2.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => input.current?.click()}><Paperclip size={19} /></button>
          <textarea aria-label="Message" className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-1 py-2.5 text-sm outline-none" placeholder="Ask about a clash or drop a Navisworks report…" rows={1} value={text} onChange={(event) => setText(event.target.value)} onKeyDown={keyDown} />
          {busy ? <button aria-label="Stop generation" className="rounded-xl bg-slate-900 p-2.5 text-white dark:bg-slate-100 dark:text-slate-900" onClick={onStop}><Square size={18} fill="currentColor" /></button> : <button aria-label="Send" className="rounded-xl bg-blue-600 p-2.5 text-white disabled:opacity-40" disabled={!text.trim() && files.length === 0} onClick={() => void submit()}><Send size={18} /></button>}
        </div>
      </div>
      <div className="pt-2 text-center text-[11px] text-slate-400">Model output is validated; verify engineering decisions before construction.</div>
    </div>
  );
}

