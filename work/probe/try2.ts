import { safeFetch } from "../../src/net-http.ts";
const terms = [
  '"distributed practice in verbal recall" [Title]',
  'Cepeda[Author] AND distributed practice[Title]',
  'Rohrer[Author] AND distributed practice',
  'Roediger[Author] AND Karpicke[Author] AND testing',
  'Dunlosky[Author] AND effective learning techniques'
];
for (const term of terms) {
  const url = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax=3&term=${encodeURIComponent(term)}`;
  try {
    const doc = await safeFetch(url, { allowedHosts: ["eutils.ncbi.nlm.nih.gov"], maxBytes: 200_000 });
    const j = JSON.parse(doc.body) as { esearchresult?: { count?: string; idlist?: string[] } };
    console.log(term, "->", j.esearchresult?.count, JSON.stringify(j.esearchresult?.idlist));
  } catch (e) { console.log(term, "FAIL", String(e).slice(0, 80)); }
}
