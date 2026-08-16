import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type { Conversation, ConversationDetail } from "../types";

export function useConversations() {
  const [items, setItems] = useState<Conversation[]>([]);
  const [active, setActive] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async (search = "") => {
    setItems(await api.listConversations(search));
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const open = useCallback(async (id: string) => {
    setActive(await api.getConversation(id));
  }, []);

  const create = useCallback(async () => {
    const conversation = await api.createConversation();
    await refresh();
    await open(conversation.id);
    return conversation;
  }, [open, refresh]);

  const update = useCallback(
    async (id: string, changes: Partial<Pick<Conversation, "title" | "archived">>) => {
      await api.updateConversation(id, changes);
      await refresh();
      if (active?.id === id) await open(id);
    },
    [active?.id, open, refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await api.deleteConversation(id);
      if (active?.id === id) setActive(null);
      await refresh();
    },
    [active?.id, refresh],
  );

  return { items, active, setActive, loading, refresh, open, create, update, remove };
}

