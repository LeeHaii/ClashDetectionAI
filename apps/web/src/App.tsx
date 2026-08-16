import { Menu, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "./api/client";
import { ChatMessage } from "./components/ChatMessage";
import { Composer } from "./components/Composer";
import { ReportPanel } from "./components/ReportPanel";
import { Sidebar } from "./components/Sidebar";
import { useConversations } from "./hooks/useConversations";
import { useSmartScroll } from "./hooks/useSmartScroll";
import type { ClashItem, Conversation, Message, Report } from "./types";

function temporaryMessage(conversationId: string, role: Message["role"], content: string): Message {
  return { id: crypto.randomUUID(), conversation_id: conversationId, role, content, status: "streaming", sequence: Date.now(), created_at: new Date().toISOString(), attachments: [] };
}

export function App() {
  const conversations = useConversations();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");
  const [search, setSearch] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [clashes, setClashes] = useState<ClashItem[]>([]);
  const [selectedClashId, setSelectedClashId] = useState<string>();
  const [activeRunId, setActiveRunId] = useState<string>();
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState<string>();
  const [batchProgress, setBatchProgress] = useState<{ completed: number; total: number } | null>(null);
  const source = useRef<EventSource | null>(null);
  const { ref: messagesRef, onScroll } = useSmartScroll(conversations.active?.messages);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => () => source.current?.close(), []);

  const activeClash = useMemo(() => clashes.find((item) => item.id === selectedClashId), [clashes, selectedClashId]);

  const appendMessage = (message: Message) => {
    conversations.setActive((current) => current ? { ...current, messages: [...current.messages, message] } : current);
  };
  const replaceMessage = (id: string, changes: Partial<Message>) => {
    conversations.setActive((current) => current ? { ...current, messages: current.messages.map((message) => message.id === id ? { ...message, ...changes } : message) } : current);
  };

  const streamRun = (runId: string, partial: Message): Promise<void> => new Promise((resolve, reject) => {
    setActiveRunId(runId);
    source.current?.close();
    const events = new EventSource(api.eventsUrl(runId));
    source.current = events;
    events.addEventListener("content.delta", (event) => {
      const { delta } = JSON.parse((event as MessageEvent).data) as { delta: string };
      partial.content += delta;
      replaceMessage(partial.id, { content: partial.content });
    });
    events.addEventListener("result.completed", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { markdown: string; assistant_message_id?: string };
      replaceMessage(partial.id, { id: payload.assistant_message_id ?? partial.id, content: payload.markdown, status: "completed" });
    });
    events.addEventListener("run.cancelled", () => replaceMessage(partial.id, { status: "cancelled" }));
    events.addEventListener("error", (event) => {
      const data = event instanceof MessageEvent ? event.data : "";
      const payload = data ? JSON.parse(data) as { message: string } : { message: "Streaming connection stopped; partial output was preserved." };
      setError(payload.message);
      replaceMessage(partial.id, { status: "failed" });
      events.close();
      setActiveRunId(undefined);
      reject(new Error(payload.message));
    });
    events.addEventListener("done", () => {
      events.close();
      source.current = null;
      setActiveRunId(undefined);
      void conversations.refresh();
      resolve();
    });
  });

  const analyze = async (text: string, files: File[], clashId = selectedClashId) => {
    setError(undefined);
    let conversation = conversations.active;
    if (!conversation) {
      const created = await api.createConversation();
      await conversations.refresh();
      await conversations.open(created.id);
      conversation = await api.getConversation(created.id);
      conversations.setActive(conversation);
    }
    const optimistic = temporaryMessage(conversation.id, "user", text);
    appendMessage(optimistic);
    const attachmentIds: string[] = [];
    for (const file of files) {
      setUploadProgress(0);
      const upload = await api.upload(file, setUploadProgress);
      attachmentIds.push(upload.id);
      if (/\.(html?|zip)$/i.test(file.name)) {
        const createdReport = await api.createReport(upload.id);
        const parsedClashes = await api.getClashes(createdReport.id);
        setReport(createdReport);
        setClashes(parsedClashes);
        setSelectedClashId(parsedClashes[0]?.id);
        clashId = parsedClashes[0]?.id;
      }
    }
    setUploadProgress(null);
    const userMessage = await api.createMessage(conversation.id, text, attachmentIds);
    replaceMessage(optimistic.id, userMessage);
    const partial = temporaryMessage(conversation.id, "assistant", "");
    appendMessage(partial);
    const run = await api.createInferenceRun(conversation.id, userMessage.id, clashId);
    await streamRun(run.id, partial);
  };

  const send = async (text: string, files: File[]) => {
    try { await analyze(text, files); } catch (failure) { setError(failure instanceof Error ? failure.message : "Request failed"); }
  };
  const stop = async () => {
    if (activeRunId) await api.cancelRun(activeRunId);
  };
  const analyzeAll = async () => {
    setBatchProgress({ completed: 0, total: clashes.length });
    for (let index = 0; index < clashes.length; index += 1) {
      const clash = clashes[index];
      setSelectedClashId(clash.id);
      try { await analyze(`Analyze clash ${clash.clash_id}.`, [], clash.id); }
      catch (failure) { setError(failure instanceof Error ? failure.message : "Batch analysis failed"); break; }
      setBatchProgress({ completed: index + 1, total: clashes.length });
    }
    setBatchProgress(null);
  };
  const download = async () => {
    if (!report) return;
    try { const artifact = await api.createPdf(report.id); window.open(api.artifactUrl(artifact.id), "_blank", "noopener,noreferrer"); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "PDF generation failed"); }
  };

  const rename = async (item: Conversation) => { const title = window.prompt("Conversation title", item.title)?.trim(); if (title) await conversations.update(item.id, { title }); };
  const remove = async (item: Conversation) => { if (window.confirm(`Delete “${item.title}”?`)) await conversations.remove(item.id); };
  const searchChanged = (value: string) => { setSearch(value); void conversations.refresh(value); };
  const regenerate = () => {
    const lastUser = [...(conversations.active?.messages ?? [])].reverse().find((message) => message.role === "user");
    if (lastUser) void send(lastUser.content, []);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <Sidebar conversations={conversations.items} activeId={conversations.active?.id} collapsed={sidebarCollapsed} dark={dark} search={search} onSearch={searchChanged} onToggle={() => setSidebarCollapsed((value) => !value)} onToggleDark={() => setDark((value) => !value)} onCreate={() => void conversations.create()} onOpen={(id) => void conversations.open(id)} onRename={(item) => void rename(item)} onArchive={(item) => void conversations.update(item.id, { archived: true })} onDelete={(item) => void remove(item)} />
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 px-4 dark:border-slate-800"><button aria-label="Toggle sidebar" className="rounded-lg p-2 hover:bg-slate-100 md:hidden dark:hover:bg-slate-900" onClick={() => setSidebarCollapsed((value) => !value)}><Menu size={20} /></button><div className="min-w-0"><div className="truncate text-sm font-semibold">{conversations.active?.title ?? "New analysis"}</div><div className="text-xs text-slate-500">{activeClash ? `${activeClash.clash_id} · ${activeClash.grid ?? "Unknown grid"}` : "Upload a report or clash image"}</div></div></header>
        {error && <div role="alert" className="flex items-center gap-2 border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-100"><TriangleAlert size={16} />{error}<button className="ml-auto" onClick={() => setError(undefined)}>Dismiss</button></div>}
        <div ref={messagesRef} onScroll={onScroll} className="flex-1 overflow-y-auto">
          {conversations.active?.messages.length ? conversations.active.messages.map((message) => <ChatMessage key={message.id} message={message} streaming={message.status === "streaming" && Boolean(activeRunId)} onRegenerate={regenerate} />) : <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center px-8 text-center"><div className="mb-4 rounded-2xl bg-blue-600 px-4 py-3 text-xl font-bold text-white">CD</div><h1 className="text-2xl font-semibold">Start a clash analysis</h1><p className="mt-2 text-sm leading-6 text-slate-500">Upload a Navisworks HTML/ZIP report or a JPG/PNG clash screenshot. Parsed metadata stays trusted while the model handles visual classification.</p></div>}
        </div>
        <Composer busy={Boolean(activeRunId)} uploadProgress={uploadProgress} onSend={send} onStop={() => void stop()} />
      </main>
      {report && <ReportPanel report={report} clashes={clashes} selectedId={selectedClashId} batchProgress={batchProgress} onSelect={setSelectedClashId} onAnalyzeSelected={() => void send(`Analyze clash ${activeClash?.clash_id ?? "selected"}.`, [])} onAnalyzeAll={() => void analyzeAll()} onDownload={() => void download()} />}
    </div>
  );
}
