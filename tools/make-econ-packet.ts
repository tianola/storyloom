import { writeFile } from "node:fs/promises";
import { safeFetch } from "../src/net-http.ts";

type Pick = { host: string; url: string; title: string; publisher: string; anchor: string; chars: number; locator: string };

const picks: Pick[] = [
  {
    host: "www.federalreserve.gov",
    url: "https://www.federalreserve.gov/faqs/economy_14400.htm",
    title: "Why does the Federal Reserve aim for inflation of 2 percent over the longer run?",
    publisher: "Board of Governors of the Federal Reserve System",
    anchor: "the Federal Open Market Committee (FOMC) judges that inflation of 2 percent",
    chars: 1_100,
    locator: "FAQ: Why does the Federal Reserve aim for inflation of 2 percent over the longer run?"
  },
  {
    host: "www.federalreserve.gov",
    url: "https://www.federalreserve.gov/economy-at-a-glance-inflation-pce.htm",
    title: "Inflation (PCE)",
    publisher: "Board of Governors of the Federal Reserve System",
    anchor: "The Federal Reserve seeks to achieve inflation at the rate of 2 percent",
    chars: 1_100,
    locator: "What is the FOMC's inflation target? / Why does the Fed target PCE inflation instead of the CPI?"
  },
  {
    host: "www.ecb.europa.eu",
    url: "https://www.ecb.europa.eu/mopo/strategy/pricestab/html/index.en.html",
    title: "Two per cent inflation target",
    publisher: "European Central Bank",
    anchor: "Governing Council, after concluding its strategy review in July 2021",
    chars: 1_200,
    locator: "sections: Two per cent inflation target / Measuring inflation - the HICP"
  },
  {
    host: "www.ecb.europa.eu",
    url: "https://www.ecb.europa.eu/mopo/strategy/strategy-review/html/price-stability-objective.en.html",
    title: "Our price stability objective and the strategy review",
    publisher: "European Central Bank",
    anchor: "The risk of deflation",
    chars: 1_200,
    locator: "section: The risk of deflation"
  }
];

const strip = (html: string) =>
  html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#x27;|&rsquo;/g, "'")
    .replace(/&#x22;|&ldquo;|&rdquo;/g, '"')
    .replace(/\s+/g, " ")
    .trim();

const retrievedAt = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
const sources = [];
for (const [index, pick] of picks.entries()) {
  const doc = await safeFetch(pick.url, { allowedHosts: [pick.host] });
  const text = strip(doc.body);
  const at = text.indexOf(pick.anchor);
  if (at < 0) throw new Error(`anchor not found on ${pick.url}: ${pick.anchor}`);
  sources.push({
    id: `src${index + 1}`,
    url: doc.url,
    title: pick.title,
    publisher: pick.publisher,
    retrievedAt,
    excerpt: text.slice(at, at + pick.chars).trim(),
    locator: pick.locator,
    snapshotHash: doc.sha256
  });
}

const packet = {
  job: {
    topic: "Why central banks aim for 2 percent inflation",
    category: "economics",
    audience: "curious general viewer",
    targetSeconds: 480,
    modelId: "qwen3.5:4b",
    voice: "af_heart"
  },
  sources
};

const out = "F:/AI-PROJECTS/longform-explainer/topics/why-central-banks-aim-for-2-percent-inflation.packet.json";
await writeFile(out, `${JSON.stringify(packet, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ out, sources: sources.map((source) => [source.id, source.excerpt.length, source.snapshotHash.slice(0, 12)]) }, null, 1));
for (const source of sources) console.log(`\n--- ${source.id} ${source.locator}\n${source.excerpt}`);
