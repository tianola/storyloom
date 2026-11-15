import { safeFetch } from "../../src/net-http.ts";
const urls = [
  "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=29106376&rettype=abstract&retmode=text",
  "https://medlineplus.gov/ency/article/002343.htm",
  "https://openstax.org/books/psychology/pages/8-3-memory-and-learning",
  "https://www.apa.org/science/about/psa/2012/01/spaced-learning"
];
for (const url of urls) {
  try {
    const doc = await safeFetch(url, { maxBytes: 4_000_000, allowedHosts: [new URL(url).hostname] });
    const plain = doc.body.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    console.log("OK", new URL(url).hostname, doc.bytes, "|", plain.slice(0, 160));
  } catch (error) {
    console.log("FAIL", new URL(url).hostname, String(error).slice(0, 90));
  }
}
