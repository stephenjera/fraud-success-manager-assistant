// Thin HTTP provider pointed at the real agent endpoint (a "stand-in" is not
// acceptable per eval-design.md). Drives a live turn: create conversation ->
// post message -> poll until terminal -> return the durable message. The agent
// can transiently fail against the LOCAL Ollama (connection reset while the
// 27B model is loading/thinking), so the turn is retried a bounded number of
// times; 3 consecutive failures is a real failure.
//
// output   = the assistant explanation (lets `is-refusal` work natively)
// metadata = the durable grounding object (sql / assumptions / tables / flags)
//            so python assertions can reason about the actual SQL.
'use strict';

const BASE = process.env.EVAL_API_BASE || 'http://127.0.0.1:8002';
const POLL_MS = 2000;
const MAX_WAIT_MS = parseInt(process.env.EVAL_TURN_TIMEOUT_MS || '240000', 10);
const MAX_ATTEMPTS = parseInt(process.env.EVAL_MAX_ATTEMPTS || '3', 10);
const RETRY_DELAY_MS = 1500;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

module.exports = class FsmAgentProvider {
  id() {
    return 'fsm-agent';
  }

  async callApi(prompt) {
    let last = null;
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      try {
        const m = await this._turn(prompt);
        if (m.status === 'success' || m.status === 'timeout') {
          return this._finish(m);
        }
        // LLM_ERROR / run error: may be local-LLM flakiness. Retry.
        last = m;
        if (attempt < MAX_ATTEMPTS) await sleep(RETRY_DELAY_MS);
      } catch (e) {
        last = { status: 'error', error: { message: String((e && e.message) || e) } };
        if (attempt < MAX_ATTEMPTS) await sleep(RETRY_DELAY_MS);
      }
    }
    return this._finish(last);
  }

  async _turn(prompt) {
    const conv = await this._j('POST', '/v1/conversations');
    const cid = conv.conversation_id;
    const msg = await this._j('POST', `/v1/conversations/${cid}/messages`, {
      text: prompt,
    });
    const mid = msg.message_id;
    const deadline = Date.now() + MAX_WAIT_MS;
    while (Date.now() < deadline) {
      const m = await this._j('GET', `/v1/conversations/${cid}/messages/${mid}`);
      if (m.status === 'success' || m.status === 'error' || m.status === 'timeout') {
        return m;
      }
      await sleep(POLL_MS);
    }
    throw new Error(`eval timeout waiting for agent turn at ${BASE}`);
  }

  async _j(method, path, body) {
    const res = await fetch(BASE + path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} ${method} ${path}`);
    return res.json();
  }

  _finish(m) {
    m = m || {};
    const g = m.grounding || null;
    const output =
      (g && g.explanation) ||
      (m.error ? `run error: ${m.error.message || m.error.code}` : String(m.status));
    return {
      output,
      metadata: {
        status: m.status,
        sql: g ? g.sql : null,
        assumptions: g ? g.assumptions : null,
        tables_and_joins_used: g ? g.tables_and_joins_used : null,
        flags: g ? g.flags : null,
        error: m.error || null,
      },
    };
  }
};
