import { Check, Copy, RotateCcw } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Message } from "../types";

interface Props {
  message: Message;
  streaming?: boolean;
  onRegenerate?(message: Message): void;
}

export function ChatMessage({ message, streaming, onRegenerate }: Props) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1_200);
  };
  return (
    <article className={`mx-auto flex w-full max-w-4xl gap-3 px-4 py-5 ${message.role === "assistant" ? "bg-slate-50/70 dark:bg-slate-900/40" : ""}`}>
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white ${message.role === "assistant" ? "bg-blue-600" : "bg-slate-700"}`}>{message.role === "assistant" ? "AI" : "You"}</div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{message.role}</div>
        <div className="markdown prose prose-slate max-w-none text-sm leading-6 dark:prose-invert">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || "Thinking…"}</ReactMarkdown>
          {streaming && <span aria-label="Streaming" className="ml-1 inline-block h-4 w-1.5 animate-pulse bg-blue-500 align-middle" />}
        </div>
        {message.attachments.length > 0 && <div className="mt-2 flex flex-wrap gap-2">{message.attachments.map((file) => <span key={file.id} className="rounded-lg bg-slate-200 px-2 py-1 text-xs dark:bg-slate-800">{file.original_filename}</span>)}</div>}
        <div className="mt-2 flex gap-1 text-slate-500">
          <button aria-label="Copy message" className="rounded p-1.5 hover:bg-slate-200 dark:hover:bg-slate-800" onClick={copy}>{copied ? <Check size={15} /> : <Copy size={15} />}</button>
          {message.role === "assistant" && onRegenerate && <button aria-label="Regenerate" className="rounded p-1.5 hover:bg-slate-200 dark:hover:bg-slate-800" onClick={() => onRegenerate(message)}><RotateCcw size={15} /></button>}
        </div>
      </div>
    </article>
  );
}

