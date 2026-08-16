import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatMessage } from "./ChatMessage";

describe("ChatMessage", () => {
  it("renders GitHub-style Markdown tables", () => {
    render(
      <ChatMessage
        message={{
          id: "message-1",
          conversation_id: "conversation-1",
          role: "assistant",
          content: "| Field | Value |\n|---|---|\n| Clash | True |",
          status: "completed",
          sequence: 1,
          created_at: new Date().toISOString(),
          attachments: [],
        }}
      />,
    );
    expect(screen.getByRole("table")).toHaveTextContent("Clash");
    expect(screen.getByRole("table")).toHaveTextContent("True");
  });
});

