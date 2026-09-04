import { test, expect } from "@playwright/test"

test.describe("STREAM_LOST recovery", () => {
  test("Send button re-enables when connection is lost mid-stream", async ({ page }) => {
    await page.goto("/")

    const sendButton = page.getByRole("button", { name: /send/i })
    const input = page.getByRole("textbox", { name: /question/i })

    await input.fill("How many transactions are in the dataset?")

    // Intercept the SSE stream and the adoptMessage fetch to simulate backend going away
    await Promise.all([
      page.route("/api/v1/runs/*/sse", async (route) => {
        // Send a tool_call.start to get the stream going
        await route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: [
            'event: tool_call.start',
            'data: {"tool": "execute_sql"}',
            "",
            'event: message.delta',
            'data: {"delta": "Looking up the data..."}',
            "",
          ].join("\n"),
        })
      }),
      page.route("/api/v1/conversations/*/messages/*", async (route) => {
        // adoptMessage fails — backend gone
        await route.fulfill({
          status: 502,
          contentType: "application/json",
          body: JSON.stringify({ error: "Bad Gateway", message: "upstream connection refused" }),
        })
      }),
      page.waitForTimeout(2000),
    ])

    // Send should be re-enabled after STREAM_LOST recovery
    await expect(sendButton).toBeEnabled()

    // Assistant bubble should show connection lost
    await expect(page.getByText(/Connection lost/i)).toBeVisible()
  })
})
