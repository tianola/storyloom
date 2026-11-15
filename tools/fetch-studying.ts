import { writeFile } from "node:fs/promises";
import { safeFetch } from "../src/net-http.ts";

const EUTILS = "https://eutils.ncbi.nlm.nih.gov";

const clean = (html: string) =>
  html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();

async function findpmid(title: string): Promise<string> {
  const url = `${EUTILS}/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&term=${encodeURIComponent(`"${title}"[Title]`)}`;
  const doc = await safeFetch(url, { allowedHosts: ["eutils.ncbi.nlm.nih.gov"], maxBytes: 200_000 });
  const parsed = JSON.parse(doc.body) as { esearchresult?: { idlist?: string[]; count?: string } };
  const id = parsed.esearchresult?.idlist?.[0];
  if (!id) throw new Error(`no pubmed id for "${title}" (count ${parsed.esearchresult?.count ?? "?"})`);
  return id;
}

async function abstract(pmid: string): Promise<{ text: string; sha256: string; bytes: number }> {
  const url = `${EUTILS}/entrez/eutils/efetch.fcgi?db=pubmed&id=${pmid}&rettype=abstract&retmode=text`;
  const doc = await safeFetch(url, { allowedHosts: ["eutils.ncbi.nlm.nih.gov"], maxBytes: 400_000 });
  return { text: clean(doc.body), sha256: doc.sha256, bytes: doc.bytes };
}

const wanted = [
  "Distributed practice in verbal recall tasks: a review and quantitative synthesis",
  "Improving students' learning with effective learning techniques: promising guidance from cognitive and educational psychology",
  "Test-enhanced learning: taking memory tests improves learning"
];

const found = [];
for (const title of wanted) {
  try {
    const pmid = await findpmid(title);
    const record = await abstract(pmid);
    found.push({ title, pmid, record });
    console.log(`PMID ${pmid} | ${record.bytes} bytes | ${record.text.slice(0, 200)}`);
  } catch (error) {
    console.log(`SKIP "${title}": ${String(error).slice(0, 120)}`);
  }
}

await writeFile("F:/AI-PROJECTS/longform-explainer/work/studying-found.json", `${JSON.stringify(found, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ kept: found.map((entry) => [entry.pmid, entry.record.sha256.slice(0, 12)]) }));
