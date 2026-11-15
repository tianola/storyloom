import { Claim, LicenseEntry, Source } from "./contracts.ts";

export type Problem = { code: string; message?: string; claimId?: string; sourceId?: string; licenseId?: string; review?: string };

export type EvidenceReport = { sources: Source[]; problems: Problem[] };

export function validateEvidence(sources: unknown[]): EvidenceReport {
  const parsed: Source[] = [];
  const problems: Problem[] = [];
  if (sources.length === 0) {
    return { sources: [], problems: [{ code: "no-sources", message: "An explainer needs at least one evidence source" }] };
  }
  const seen = new Set<string>();
  for (const candidate of sources) {
    const result = Source.safeParse(candidate);
    if (!result.success) {
      problems.push({ code: "invalid-source", message: result.error.issues[0]?.message ?? "unparsable source" });
      continue;
    }
    if (seen.has(result.data.id)) {
      problems.push({ code: "duplicate-source-id", sourceId: result.data.id });
      continue;
    }
    seen.add(result.data.id);
    parsed.push(result.data);
  }
  return { sources: parsed, problems };
}

export type ReviewRecord = { reviewer: string; reviewedAt: string };

export function withReviews(claims: unknown[], reviews: Record<string, ReviewRecord>): { claims: unknown[]; problems: Problem[] } {
  const problems: Problem[] = [];
  const cited = new Set<string>();
  const merged = claims.map((candidate) => {
    const value = candidate as { id?: unknown; review?: unknown } | null;
    if (!value || typeof value.id !== "string") return candidate;
    cited.add(value.id);
    if (value.review !== "approved") return candidate;
    const record = reviews[value.id];
    if (!record) {
      problems.push({ code: "missing-review-record", claimId: value.id });
      return candidate;
    }
    return { ...(candidate as object), reviewer: record.reviewer, reviewedAt: record.reviewedAt };
  });
  for (const claimId of Object.keys(reviews)) {
    if (!cited.has(claimId)) problems.push({ code: "orphan-review", claimId });
  }
  return { claims: merged, problems };
}

export function validateClaims(claims: unknown[], sources: Source[]): { claims: Claim[]; problems: Problem[] } {
  const known = new Set(sources.map((source) => source.id));
  const parsed: Claim[] = [];
  const problems: Problem[] = [];
  for (const candidate of claims) {
    const result = Claim.safeParse(candidate);
    if (!result.success) {
      problems.push({ code: "invalid-claim", message: result.error.issues[0]?.message ?? "unparsable claim" });
      continue;
    }
    const claim = result.data;
    let broken = false;
    for (const evidence of claim.evidence) {
      if (!known.has(evidence.sourceId)) {
        problems.push({ code: "unknown-source", claimId: claim.id, sourceId: evidence.sourceId });
        broken = true;
      }
    }
    if (claim.review === "approved" && (!("reviewer" in claim) || !("reviewedAt" in claim))) {
      problems.push({ code: "missing-reviewer", claimId: claim.id });
      broken = true;
    }
    if (!broken) parsed.push(claim);
  }
  return { claims: parsed, problems };
}

export function validateLicenses(licenses: unknown[]): { licenses: LicenseEntry[]; problems: Problem[] } {
  const parsed: LicenseEntry[] = [];
  const problems: Problem[] = [];
  for (const candidate of licenses) {
    const result = LicenseEntry.safeParse(candidate);
    if (result.success) parsed.push(result.data);
    else problems.push({ code: "invalid-license", message: result.error.issues[0]?.message ?? "unparsable license" });
  }
  return { licenses: parsed, problems };
}

export type ExportGate = { ready: boolean; blockers: Problem[]; warnings: Problem[] };

export async function verifySnapshots(sources: Source[], digest: (path: string) => Promise<string>): Promise<Problem[]> {
  const problems: Problem[] = [];
  for (const source of sources) {
    if (!source.url?.startsWith("file://")) continue;
    const path = new URL(source.url).pathname.replace(/^\//, "");
    const hash = await digest(path).catch(() => null);
    if (hash === null) problems.push({ code: "snapshot-missing", sourceId: source.id, message: path });
    else if (hash !== source.snapshotHash) problems.push({ code: "snapshot-hash-mismatch", sourceId: source.id, message: `disk ${hash}` });
  }
  return problems;
}
export function exportGate(input: { claims: Claim[]; licenses: LicenseEntry[] }): ExportGate {
  const blockers: Problem[] = [];
  const warnings: Problem[] = [];
  for (const claim of input.claims) {
    if (claim.review === "rejected") blockers.push({ code: "rejected-claim", claimId: claim.id });
    else if (claim.review === "unreviewed") {
      if (claim.material) blockers.push({ code: "unreviewed-material-claim", claimId: claim.id });
      else warnings.push({ code: "unreviewed-claim", claimId: claim.id });
    }
  }
  for (const license of input.licenses) {
    if (license.review !== "approved") blockers.push({ code: "license-not-approved", licenseId: license.id, review: license.review });
  }
  return { ready: blockers.length === 0, blockers, warnings };
}
