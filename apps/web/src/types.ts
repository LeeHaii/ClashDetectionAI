export interface Attachment {
  id: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: string;
  sequence: number;
  created_at: string;
  attachments: Attachment[];
}

export interface Conversation {
  id: string;
  title: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface Report {
  id: string;
  source_attachment_id: string;
  original_filename: string;
  title: string;
  parse_status: "pending" | "completed" | "partial" | "failed";
  parser_version: string;
  errors: Array<{ row_index: number; message: string }>;
  clash_count: number;
  created_at: string;
}

export interface ElementMetadata {
  element_id: string | null;
  layer: string | null;
  size: string | null;
}

export interface ClashItem {
  id: string;
  report_id: string;
  clash_id: string;
  row_index: number;
  image_path: string | null;
  distance_raw: string | null;
  distance_m: number | null;
  grid: string | null;
  clash_point: string | null;
  elements: ElementMetadata[];
  source_metadata: Record<string, unknown>;
}

export interface InferenceRun {
  id: string;
  status: "pending" | "running" | "completed" | "cancelled" | "failed";
  error: string | null;
}

export interface Artifact {
  id: string;
  report_id: string;
  status: "pending" | "completed" | "failed";
  error: string | null;
}

