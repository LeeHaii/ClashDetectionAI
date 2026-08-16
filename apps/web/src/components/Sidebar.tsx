import { Archive, Menu, Moon, Pencil, Plus, Search, Sun, Trash2, X } from "lucide-react";

import type { Conversation } from "../types";

interface Props {
  conversations: Conversation[];
  activeId?: string;
  collapsed: boolean;
  dark: boolean;
  search: string;
  onSearch(value: string): void;
  onToggle(): void;
  onToggleDark(): void;
  onCreate(): void;
  onOpen(id: string): void;
  onRename(item: Conversation): void;
  onArchive(item: Conversation): void;
  onDelete(item: Conversation): void;
}

export function Sidebar(props: Props) {
  if (props.collapsed) {
    return (
      <aside className="flex w-14 shrink-0 flex-col items-center border-r border-slate-200 bg-slate-50 py-3 dark:border-slate-800 dark:bg-slate-950">
        <button aria-label="Open sidebar" className="rounded-lg p-2 hover:bg-slate-200 dark:hover:bg-slate-800" onClick={props.onToggle}><Menu size={20} /></button>
        <button aria-label="New conversation" className="mt-3 rounded-lg bg-blue-600 p-2 text-white" onClick={props.onCreate}><Plus size={20} /></button>
      </aside>
    );
  }
  return (
    <aside className="absolute inset-y-0 z-20 flex w-72 shrink-0 flex-col border-r border-slate-200 bg-slate-50 p-3 shadow-xl md:static md:shadow-none dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center justify-between px-1 py-2">
        <div><div className="font-semibold">ClashDetectionAI</div><div className="text-xs text-slate-500">BIM coordination workspace</div></div>
        <button aria-label="Close sidebar" className="rounded-lg p-2 hover:bg-slate-200 dark:hover:bg-slate-800" onClick={props.onToggle}><X size={19} /></button>
      </div>
      <button className="my-3 flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-3 py-2.5 font-medium text-white hover:bg-blue-700" onClick={props.onCreate}><Plus size={18} /> New conversation</button>
      <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-900">
        <Search size={16} className="text-slate-400" />
        <input aria-label="Search conversations" className="min-w-0 flex-1 bg-transparent text-sm outline-none" placeholder="Search" value={props.search} onChange={(event) => props.onSearch(event.target.value)} />
      </label>
      <div className="mt-3 flex-1 space-y-1 overflow-y-auto">
        {props.conversations.map((item) => (
          <div key={item.id} className={`group flex items-center rounded-xl ${item.id === props.activeId ? "bg-blue-100 text-blue-950 dark:bg-blue-950 dark:text-blue-100" : "hover:bg-slate-200 dark:hover:bg-slate-900"}`}>
            <button className="min-w-0 flex-1 truncate px-3 py-2.5 text-left text-sm" onClick={() => props.onOpen(item.id)}>{item.title}</button>
            <div className="hidden items-center pr-1 group-hover:flex">
              <button aria-label="Rename" className="p-1.5" onClick={() => props.onRename(item)}><Pencil size={14} /></button>
              <button aria-label="Archive" className="p-1.5" onClick={() => props.onArchive(item)}><Archive size={14} /></button>
              <button aria-label="Delete" className="p-1.5 text-red-600" onClick={() => props.onDelete(item)}><Trash2 size={14} /></button>
            </div>
          </div>
        ))}
      </div>
      <button className="mt-3 flex items-center gap-2 rounded-xl px-3 py-2 text-sm hover:bg-slate-200 dark:hover:bg-slate-900" onClick={props.onToggleDark}>
        {props.dark ? <Sun size={17} /> : <Moon size={17} />} {props.dark ? "Light mode" : "Dark mode"}
      </button>
    </aside>
  );
}

