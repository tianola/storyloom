import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import { test } from "node:test";
import type { AddressInfo } from "node:net";
import { assertLocalModelHost, generateJson, OllamaError } from "../src/ollama.ts";

type Reply = (res: import("node:http").ServerResponse) => void;

async function withServer(reply: Reply, run: (host: string, calls: unknown[]) => Promise<void>): Promise<void> {
  const calls: unknown[] = [];
  const server: Server = createServer((req, res) => {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      calls.push(JSON.parse(body));
      reply(res);
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = (server.address() as AddressInfo).port;
  try {
    await run(`http://127.0.0.1:${port}`, calls);
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
}

function ndjson(lines: unknown[]): string {
  return lines.map((line) => `${JSON.stringify(line)}\n`).join("");
}

test("only a loopback model host is allowed", () => {
  assert.equal(assertLocalModelHost("http://127.0.0.1:11435"), "http://127.0.0.1:11435");
  assert.equal(assertLocalModelHost("http://localhost:11434"), "http://localhost:11434");
  assert.equal(assertLocalModelHost("http://[::1]:11435"), "http://[::1]:11435");
  for (const bad of ["https://api.example.com/v1", "http://10.0.0.5:11434", "http://169.254.169.254:11434", "not a url"]) {
    assert.throws(() => assertLocalModelHost(bad), OllamaError, bad);
  }
});

test("streaming generate accumulates chunks and reports token usage", async () => {
  await withServer(
    (res) => {
      res.writeHead(200, { "content-type": "application/x-ndjson" });
      res.write(ndjson([{ model: "m", response: '{"a', done: false }]));
      res.write(ndjson([{ model: "m", response: '":1}', done: false }]));
      res.end(ndjson([{ model: "m", response: "", done: true, done_reason: "stop", eval_count: 42, prompt_eval_count: 7, eval_duration: 1_000_000_000, prompt_eval_duration: 1_000_000_000 }]));
    },
    async (host, calls) => {
      const result = await generateJson({ host, model: "m", system: "sys", prompt: "usr", seed: 7, numCtx: 8192, numPredict: 2000 });
      assert.equal(result.text, '{"a":1}');
      assert.equal(result.completionTokens, 42);
      assert.equal(result.promptTokens, 7);
      assert.equal(result.tokensPerSecond, 42);
      assert.equal(result.truncated, false);
      assert.deepEqual(calls[0], {
        model: "m",
        system: "sys",
        prompt: "usr",
        stream: true,
        format: "json",
        options: { temperature: 0.4, num_ctx: 8192, num_predict: 2000, seed: 7 }
      });
    }
  );
});

test("a completion cut off by the context window is reported, not silently parsed", async () => {
  await withServer(
    (res) => {
      res.writeHead(200, { "content-type": "application/x-ndjson" });
      res.end(ndjson([{ response: '{"a"', done: true, done_reason: "length", eval_count: 8192, prompt_eval_count: 100 }]));
    },
    async (host) => {
      const result = await generateJson({ host, model: "m", system: "s", prompt: "p", seed: 7, numCtx: 8192, numPredict: 8192 });
      assert.equal(result.truncated, true);
      assert.equal(result.text, '{"a"');
    }
  );
});

test("the delta callback sees every streamed chunk", async () => {
  await withServer(
    (res) => {
      res.writeHead(200, { "content-type": "application/x-ndjson" });
      res.end(ndjson([{ response: "one " }, { response: "two" }, { response: "", done: true, done_reason: "stop", eval_count: 3, prompt_eval_count: 3 }]));
    },
    async (host) => {
      const seen: string[] = [];
      const result = await generateJson({ host, model: "m", system: "s", prompt: "p", seed: 1, numCtx: 2048, numPredict: 64, onDelta: (delta) => seen.push(delta) });
      assert.equal(result.text, "one two");
      assert.deepEqual(seen, ["one ", "two", ""]);
    }
  );
});

test("think:false is sent through and reasoning text is counted separately from the answer", async () => {
  await withServer(
    (res) => {
      res.writeHead(200, { "content-type": "application/x-ndjson" });
      res.end(ndjson([
        { thinking: "hidden chain of thought", response: "", done: false },
        { response: '{"ok":true}', done: false },
        { response: "", done: true, done_reason: "stop", eval_count: 30, prompt_eval_count: 10 }
      ]));
    },
    async (host, calls) => {
      const result = await generateJson({ host, model: "m", system: "s", prompt: "p", seed: 7, numCtx: 2048, numPredict: 64, think: false });
      assert.equal(result.text, '{"ok":true}', "reasoning text must not be glued onto the answer");
      assert.equal(result.thinkingChars, "hidden chain of thought".length);
      assert.deepEqual(calls[0], {
        model: "m",
        system: "s",
        prompt: "p",
        stream: true,
        format: "json",
        think: false,
        options: { temperature: 0.4, num_ctx: 2048, num_predict: 64, seed: 7 }
      });
    }
  );
});

test("a reply that is only reasoning is reported as empty rather than as bad json", async () => {
  await withServer(
    (res) => {
      res.writeHead(200, { "content-type": "application/x-ndjson" });
      res.end(ndjson([{ thinking: "lots of thought", response: "", done: true, done_reason: "length", eval_count: 2000, prompt_eval_count: 900 }]));
    },
    async (host) => {
      const result = await generateJson({ host, model: "m", system: "s", prompt: "p", seed: 7, numCtx: 8192, numPredict: 2000 });
      assert.equal(result.text, "");
      assert.equal(result.truncated, true);
      assert.ok(result.thinkingChars > 0);
    }
  );
});

test("a server error becomes an OllamaError that carries the status", async () => {
  await withServer(
    (res) => {
      res.writeHead(500, { "content-type": "text/plain" });
      res.end("model load failed");
    },
    async (host) => {
      await assert.rejects(
        () => generateJson({ host, model: "m", system: "s", prompt: "p", seed: 1, numCtx: 2048, numPredict: 64 }),
        (error: unknown) => error instanceof OllamaError && /\b500\b/.test(String(error))
      );
    }
  );
});

test("a stalled stream is cut after the idle deadline instead of hanging forever", async () => {
  let connected = 0;
  const server = createServer((_req, res) => {
    connected += 1;
    res.writeHead(200, { "content-type": "application/x-ndjson" });
    res.write(ndjson([{ response: "partial", done: false }]));
    // never finishes: the idle guard has to notice
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const host = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  try {
    await assert.rejects(
      () => generateJson({ host, model: "m", system: "s", prompt: "p", seed: 1, numCtx: 2048, numPredict: 64, idleMs: 200, maxAttempts: 1 }),
      (error: unknown) => error instanceof OllamaError && /idle/i.test(String(error))
    );
  } finally {
    server.close();
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  assert.equal(connected, 1);
});

test("a transport failure is retried once before failing", async () => {
  let attempts = 0;
  const server = createServer((req, res) => {
    attempts += 1;
    req.resume();
    res.writeHead(502, { "content-type": "text/plain" });
    res.end("upstream down");
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const host = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  try {
    await assert.rejects(() => generateJson({ host, model: "m", system: "s", prompt: "p", seed: 1, numCtx: 2048, numPredict: 64, retryMs: 10 }));
  } finally {
    server.close();
  }
  assert.equal(attempts, 3);
});
