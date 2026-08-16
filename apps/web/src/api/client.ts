import type {
  Artifact,
  Attachment,
  ClashItem,
  Conversation,
  ConversationDetail,
  InferenceRun,
  Message,
  Report,
} from "../types";

export const API_ROOT = (import.meta.env.VITE_API_URL ?? "http://localhost:8000/api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `Request failed with ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  listConversations(search = "") {
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    return request<Conversation[]>(`/conversations${query}`);
  },
  createConversation(title = "New conversation") {
    return request<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  },
  getConversation(id: string) {
    return request<ConversationDetail>(`/conversations/${id}`);
  },
  updateConversation(id: string, changes: Partial<Pick<Conversation, "title" | "archived">>) {
    return request<Conversation>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    });
  },
  deleteConversation(id: string) {
    return request<void>(`/conversations/${id}`, { method: "DELETE" });
  },
  createMessage(conversationId: string, content: string, attachmentIds: string[]) {
    return request<Message>(`/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, attachment_ids: attachmentIds }),
    });
  },
  upload(file: File, onProgress: (percentage: number) => void): Promise<Attachment> {
    return new Promise((resolve, reject) => {
      const body = new FormData();
      body.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_ROOT}/uploads`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
      };
      xhr.onerror = () => reject(new Error("Upload connection failed"));
      xhr.onload = () => {
        const payload = JSON.parse(xhr.responseText || "{}");
        if (xhr.status >= 200 && xhr.status < 300) resolve(payload as Attachment);
        else reject(new Error(payload.detail ?? `Upload failed with ${xhr.status}`));
      };
      xhr.send(body);
    });
  },
  createReport(uploadId: string, title?: string) {
    return request<Report>("/reports", {
      method: "POST",
      body: JSON.stringify({ upload_id: uploadId, title }),
    });
  },
  getClashes(reportId: string) {
    return request<ClashItem[]>(`/reports/${reportId}/clashes`);
  },
  createInferenceRun(conversationId: string, userMessageId: string, clashItemId?: string) {
    return request<InferenceRun>("/inference-runs", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: conversationId,
        user_message_id: userMessageId,
        clash_item_id: clashItemId,
      }),
    });
  },
  cancelRun(runId: string) {
    return request<InferenceRun>(`/inference-runs/${runId}/cancel`, { method: "POST" });
  },
  createPdf(reportId: string) {
    return request<Artifact>(`/reports/${reportId}/pdf`, { method: "POST" });
  },
  eventsUrl(runId: string) {
    return `${API_ROOT}/inference-runs/${runId}/events`;
  },
  imageUrl(clashId: string) {
    return `${API_ROOT}/clashes/${clashId}/image`;
  },
  artifactUrl(artifactId: string) {
    return `${API_ROOT}/artifacts/${artifactId}/download`;
  },
};

