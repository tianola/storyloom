import { safeFetch } from "../src/net-http.ts";

const [url, allowedCsv = "", offset = "0"] = process.argv.slice(2);
if (!url) {
  console.error("usage: node tools/fetch-evidence.ts <url> [allowedHosts,csv] [textOffset]");
  process.exit(2);
}
try {
  const doc = await safeFetch(url, { allowedHosts: allowedCsv.split(",").filter(Boolean) });
  const text = doc.body
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const start = Number(offset);
  console.log(JSON.stringify({ url: doc.url, status: doc.status, bytes: doc.bytes, sha256: doc.sha256, textChars: text.length, excerpt: text.slice(start, start + 1600) }, null, 2));
} catch (error) {
  console.error(`fetch failed: ${(error as Error).message}`);
  process.exit(1);
}
