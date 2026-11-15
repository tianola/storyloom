import { assertLocalModelHost } from "./ollama.ts";

export type ChatInput = {
  host: string;
  model: string;
  apiKey?: string;
  system: string;
  prompt: string;
  maxTokens: number;
  temperature?: number;
  /** Route-specific extras merged into the payload, e.g. reasoning_effort or thinking:{type:"disabled"}. */
  extra?: Record<string, unknown>;
  idleMs?: number;
  maxAttempts?: number;
  retryMs?: number;
  onDelta?: (text: string) => void;
};

export type ChatResult = {
  text: string;
  promptTokens: number;
  completionTokens: number;
  seconds: number;
  tokensPerSecond: number;
  thinkingChars: number;
  truncated: boolean;
  attempts: number;
};

export class ChatError extends Error {}

type DeltaChunk = {
  choices?: { delta?: { content?: string | null; reasoning_content?: string | null }; finish_reason?: string | null }[];
  usage?: { prompt_tokens?: number; completion_tokens?: number };
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const MAX_QUOTA_WAIT_SECONDS = 3600;

/** The gateway's free tier is one shared bucket, not a per-model one: measured 2026-11-06, every `openrouter/…:free`
 * route answered 429 naming the same quota and the same `reset_at`, so a longer model chain cannot dodge it. Returns the
 * seconds worth waiting, zero when the window has already passed, or null when this is not a quota block. */
export function quotaWaitSeconds(error: unknown): number | null {
  const message = error instanceof Error ? error.message : String(error);
  if (!message.includes("429")) return null;
  const resetAt = /"reset_at"\s*:\s*"([^"]+)"/u.exec(message)?.[1];
  if (resetAt) {
    const at = Date.parse(resetAt);
    if (Number.isFinite(at)) return Math.min(MAX_QUOTA_WAIT_SECONDS, Math.max(0, Math.round((at - Date.now()) / 1000)));
  }
  const retry = Number(/"retry_after"\s*:\s*(\d+)/u.exec(message)?.[1] ?? "");
  return Number.isFinite(retry) && retry > 0 ? Math.min(MAX_QUOTA_WAIT_SECONDS, retry) : null;
}

async function streamOnce(input: ChatInput, base: string, payload: unknown): Promise<{ text: string; thinkingChars: number; finish: string; usage: DeltaChunk["usage"] }> {
  const idleMs = input.idleMs ?? 120_000;
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
    const response = await fetch(`${base}/chat/completions`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "text/event-stream",
        ...(input.apiKey ? { authorization: `Bearer ${input.apiKey}` } : {})
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    touch();
    if (!response.ok) {
      const detail = (await response.text().catch(() => "")).slice(0, 300);
      throw new ChatError(`${response.status}: ${detail}`);
    }
    if (!response.body) throw new ChatError("the gateway returned an empty body");
    const decoder = new TextDecoder();
    const parts: string[] = [];
    let thinkingChars = 0;
    let buffer = "";
    let finish = "";
    let usage: DeltaChunk["usage"];
    const consume = (data: string) => {
      if (data === "[DONE]") return;
      let chunk: DeltaChunk;
      try {
        chunk = JSON.parse(data) as DeltaChunk;
      } catch {
        throw new ChatError(`the gateway sent an event that is not json: ${data.slice(0, 120)}`);
      }
      if (chunk.usage) usage = chunk.usage;
      for (const choice of chunk.choices ?? []) {
        if (typeof choice.delta?.reasoning_content === "string") thinkingChars += choice.delta.reasoning_content.length;
        if (typeof choice.delta?.content === "string") {
          parts.push(choice.delta.content);
          input.onDelta?.(choice.delta.content);
        }
        if (choice.finish_reason) finish = choice.finish_reason;
      }
    };
    for await (const raw of response.body as AsyncIterable<Uint8Array>) {
      touch();
      buffer += decoder.decode(raw, { stream: true });
      let newline = buffer.indexOf("\n");
      while (newline >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        newline = buffer.indexOf("\n");
        if (line.startsWith("data:")) consume(line.slice(5).trim());
      }
    }
    const tail = buffer.trim();
    if (tail.startsWith("data:")) consume(tail.slice(5).trim());
    if (parts.length === 0 && finish === "") throw new ChatError("the stream ended without any content or finish reason");
    return { text: parts.join(""), thinkingChars, finish, usage };
  } catch (error) {
    if (idleReason !== "") throw new ChatError(idleReason);
    if (error instanceof ChatError) throw error;
    const cause = error instanceof Error && error.cause instanceof Error ? ` (${error.cause.name})` : "";
    throw new ChatError(`request to ${base} failed: ${error instanceof Error ? error.message : String(error)}${cause}`);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/**
 * OpenAI-compatible chat completion for the drafting calls, streamed so an idle gateway is reported as an idle stream
 * instead of a header timeout. JSON mode is requested, and a reply that arrives fenced in ```json fences is unwrapped
 * because not every route honours the response format the same way.
 */
export async function generateJsonChat(input: ChatInput): Promise<ChatResult> {
  const trimmed = assertLocalModelHost(input.host).replace(/\/+$/, "");
  const base = trimmed.endsWith("/v1") ? trimmed : `${trimmed}/v1`;
  if (input.model.trim() === "") throw new ChatError("a concrete model id is required");
  const payload = {
    model: input.model,
    stream: true,
    stream_options: { include_usage: true },
    response_format: { type: "json_object" },
    temperature: input.temperature ?? 0.4,
    max_tokens: input.maxTokens,
    ...(input.extra ?? {}),
    messages: [
      { role: "system", content: input.system },
      { role: "user", content: input.prompt }
    ]
  };
  const started = Date.now();
  const maxAttempts = input.maxAttempts ?? 2;
  let lastError = "";
  let streamed: Awaited<ReturnType<typeof streamOnce>> | null = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      streamed = await streamOnce(input, base, payload);
      break;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
      if (attempt < maxAttempts) await sleep(input.retryMs ?? 2_000);
    }
  }
  if (!streamed) throw new ChatError(`${input.model} failed after ${maxAttempts} attempts: ${lastError}`);
  const seconds = (Date.now() - started) / 1000;
  const text = streamed.text.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  const completionTokens = streamed.usage?.completion_tokens ?? Math.round(text.length / 3.4);
  return {
    text,
    promptTokens: streamed.usage?.prompt_tokens ?? 0,
    completionTokens,
    seconds,
    tokensPerSecond: seconds > 0 ? Math.round((completionTokens / seconds) * 100) / 100 : 0,
    thinkingChars: streamed.thinkingChars,
    truncated: streamed.finish === "length",
    attempts: 1
  };
}
