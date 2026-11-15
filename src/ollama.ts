export class OllamaError extends Error {}

export type GenerateInput = {
  host: string;
  model: string;
  system: string;
  prompt: string;
  seed: number;
  numCtx: number;
  numPredict: number;
  temperature?: number;
  think?: boolean;
  idleMs?: number;
  maxAttempts?: number;
  retryMs?: number;
  onDelta?: (delta: string) => void;
};

export type GenerateResult = {
  text: string;
  promptTokens: number;
  completionTokens: number;
  seconds: number;
  tokensPerSecond: number;
  thinkingChars: number;
  truncated: boolean;
  attempts: number;
};

const LOOPBACK = new Set(["localhost", "127.0.0.1", "::1"]);

export function assertLocalModelHost(host: string): string {
  let url: URL;
  try {
    url = new URL(host);
  } catch {
    throw new OllamaError(`model host is not a url: ${host}`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new OllamaError(`model host protocol not allowed: ${url.protocol}`);
  const hostname = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
  const loopback = LOOPBACK.has(hostname) || /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname);
  if (!loopback) throw new OllamaError(`drafting sends the topic and evidence to the model server; only a loopback host is allowed, got ${hostname}`);
  return host.replace(/\/+$/, "");
}

function rate(tokens: number, durationNs: number): number {
  if (!(durationNs > 0) || !(tokens > 0)) return 0;
  return Math.round(tokens / (durationNs / 1e9) * 100) / 100;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

type FinalChunk = {
  response?: string;
  thinking?: string;
  done?: boolean;
  done_reason?: string;
  eval_count?: number;
  prompt_eval_count?: number;
  eval_duration?: number;
  prompt_eval_duration?: number;
};

async function streamOnce(input: GenerateInput, base: string, payload: unknown): Promise<{ text: string; thinkingChars: number; final: FinalChunk }> {
  const idleMs = input.idleMs ?? 180_000;
  const controller = new AbortController();
  let idleReason = "";
  let timer: NodeJS.Timeout | undefined;
  const touch = () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      idleReason = `stream idle: no token from ${base} for ${idleMs} ms`;
      controller.abort();
    }, idleMs);
  };
  touch();
  try {
    const response = await fetch(`${base}/api/generate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    touch();
    if (!response.ok) {
      const detail = (await response.text().catch(() => "")).slice(0, 400);
      throw new OllamaError(`ollama responded ${response.status}: ${detail}`);
    }
    if (!response.body) throw new OllamaError("ollama returned an empty body");
    const decoder = new TextDecoder();
    const parts: string[] = [];
    let thinkingChars = 0;
    let buffer = "";
    let final: FinalChunk = {};
    for await (const raw of response.body as AsyncIterable<Uint8Array>) {
      touch();
      buffer += decoder.decode(raw, { stream: true });
      let newline = buffer.indexOf("\n");
      while (newline >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        newline = buffer.indexOf("\n");
        if (line === "") continue;
        let chunk: FinalChunk;
        try {
          chunk = JSON.parse(line) as FinalChunk;
        } catch {
          throw new OllamaError(`ollama sent a line that is not json: ${line.slice(0, 120)}`);
        }
        if (typeof chunk.thinking === "string") thinkingChars += chunk.thinking.length;
        if (typeof chunk.response === "string") {
          parts.push(chunk.response);
          input.onDelta?.(chunk.response);
        }
        if (chunk.done) final = chunk;
      }
    }
    const tail = buffer.trim();
    if (tail !== "") {
      const chunk = JSON.parse(tail) as FinalChunk;
      if (typeof chunk.thinking === "string") thinkingChars += chunk.thinking.length;
      if (typeof chunk.response === "string") parts.push(chunk.response);
      if (chunk.done) final = chunk;
    }
    if (!final.done) throw new OllamaError("ollama stream ended before the done marker");
    return { text: parts.join(""), thinkingChars, final };
  } catch (error) {
    if (idleReason !== "") throw new OllamaError(idleReason);
    if (error instanceof OllamaError) throw error;
    const cause = error instanceof Error && error.cause instanceof Error ? ` (${error.cause.name})` : "";
    throw new OllamaError(`request to ${base} failed: ${error instanceof Error ? error.message : String(error)}${cause}`);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export async function generateJson(input: GenerateInput): Promise<GenerateResult> {
  const base = assertLocalModelHost(input.host);
  if (input.model.trim() === "") throw new OllamaError("a concrete model id is required");
  const payload = {
    model: input.model,
    system: input.system,
    prompt: input.prompt,
    stream: true,
    format: "json",
    ...(input.think === undefined ? {} : { think: input.think }),
    options: {
      temperature: input.temperature ?? 0.4,
      num_ctx: input.numCtx,
      num_predict: input.numPredict,
      seed: input.seed
    }
  };
  const maxAttempts = input.maxAttempts ?? 3;
  const retryMs = input.retryMs ?? 2_000;
  const started = Date.now();
  let lastError: OllamaError | undefined;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const { text, thinkingChars, final } = await streamOnce(input, base, payload);
      return {
        text,
        promptTokens: final.prompt_eval_count ?? 0,
        completionTokens: final.eval_count ?? 0,
        seconds: (Date.now() - started) / 1000,
        tokensPerSecond: rate(final.eval_count ?? 0, final.eval_duration ?? 0),
        thinkingChars,
        truncated: final.done_reason === "length",
        attempts: attempt
      };
    } catch (error) {
      lastError = error instanceof OllamaError ? error : new OllamaError(String(error));
      if (attempt < maxAttempts) await sleep(retryMs * attempt);
    }
  }
  throw lastError ?? new OllamaError(`request to ${base} failed`);
}
