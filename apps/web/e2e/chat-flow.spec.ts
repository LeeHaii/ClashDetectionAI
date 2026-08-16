import { expect, test } from "@playwright/test";

test("creates a conversation shell and accepts a report attachment", async ({ page }) => {
  await page.route("http://localhost:8000/api/conversations**", async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill({ json: [] });
    } else {
      await route.fulfill({
        status: 201,
        json: {
          id: "conversation-1",
          title: "New conversation",
          archived: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });
    }
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Start a clash analysis" })).toBeVisible();
  await expect(page.getByLabel("Message")).toBeVisible();
  await expect(page.getByRole("button", { name: "Attach files" })).toBeVisible();
});

