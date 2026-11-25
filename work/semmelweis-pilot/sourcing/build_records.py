"""archive.json + assets/archive-licence.json for work/semmelweis-pilot (Commons stills, all public domain by age)."""
import json, re
from pathlib import Path
EP = Path('.').resolve() / 'work' / 'semmelweis-pilot'
info = json.loads((EP / 'sourcing/info-stills.json').read_text(encoding='utf-8'))
# key, carries, depicts, light_side, pan, year, credit, purpose, derivative note
S = [
 ('semmelweis-portrait', 'real_person', ['Semmelweis'], 'left', 1.2, 1860,
  "After Jenő Doby (engraving, 1860), scan from Benedek 1983 / Wikimedia Commons (public domain)",
  "Ignaz Semmelweis in 1860, as an engraved portrait (a scan of a flat public domain work)"),
 ('akh-engraving', 'real_place', ['General Hospital'], 'left', -1.2, 1784,
  "Joseph and Peter Schaffer, c. 1784 (via Dorotheum) / Wikimedia Commons (public domain)",
  "the Vienna General Hospital (Allgemeines Krankenhaus) at its opening: 'Aussicht des Allgemeinen Krankenhauses', coloured copper engraving by Joseph and Peter Schaffer (a photograph of a flat public domain work)"),
 ('aetiologie-1861', 'period_look', ['Semmelweis', 'book'], 'right', 1.2, 1861,
  "Ignaz Semmelweis, Die Aetiologie, der Begriff und die Prophylaxis des Kindbettfiebers, 1861 / Wikimedia Commons (public domain)",
  "the title page of Semmelweis's 1861 book on the cause and prevention of childbed fever (a scan of a flat public domain work)"),
 ('kolletschka-portrait', 'real_person', ['Kolletschka'], 'right', -1.2, 1844,
  "Josef Kriehuber (lithograph, 1844), photographed at the Albertina / Wikimedia Commons (public domain)",
  "Jakob Kolletschka, lithograph portrait by Josef Kriehuber, 1844 (a photograph of a flat public domain work)"),
]
records, rows = {}, []
for i, (key, carries, dep, side, pan, year, credit, purpose) in enumerate(S, 1):
    src = info[key]; ident = f"arch-{i:03d}"
    asset = f"assets/archive/{key}.jpg"
    records[key] = {"asset": asset, "licence": ident, "form": "still", "aspect": "pillarbox_visible_edge",
        "treatment": "keep_distinct", "light_side": side, "carries": carries, "depicts": dep,
        "still_move": {"pan_deg": pan, "zoom_from": 1.03, "zoom_to": 1.14}}
    rows.append({"id": ident, "provider": "Wikimedia Commons", "license": "Public domain", "url": src['page'], "file": asset,
        "source_archive": "Wikimedia Commons", "rights_basis": "pd_expired", "credit_line": credit,
        "retrieval_url": re.sub(r'\?.*$', '', src['url']), "retrieved_date": "2026-11-21",
        "purpose_of_use": f"archival evidence for semmelweis-pilot: {purpose}",
        "third_party_rights": "none", "in_timecode": "00:00:00:00", "out_timecode": "00:00:06:00", "timebase": 30,
        "source_frame_rate": 30.0, "licence_version": f"public domain (created {year}; author died before 1930)",
        "obligations": [], "qc_watermark": False, "derivative_transformations": [], "uploaded_as_is": True, "source_year": year})
(EP / 'archive.json').write_text(json.dumps(records, indent=1, ensure_ascii=False), encoding='utf-8')
(EP / 'assets/archive-licence.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf-8')
