"""archive.json, the rights ledger and script/shots-hint.json for the story cut of work/ask-chatgpt.

Archive is evidence, not texture (workflow/style.json archive.evidence): every record names in `depicts` the
specific thing it shows, and plays only under the line that names it. The generic data-centre clips of the
first cut are gone. Run from the repository root after the narration is synthesised.
"""
import json
import re
from pathlib import Path

EP = Path('.').resolve() / 'work' / 'ask-chatgpt'
info = json.loads((EP / 'sourcing/info.json').read_text(encoding='utf-8'))
info.update(json.loads((EP / 'sourcing/info-stills.json').read_text(encoding='utf-8')))
cuts = json.loads((EP / 'sourcing/cuts.json').read_text(encoding='utf-8'))


def tc(sec, fps):
    f = int(round(sec * fps))
    return f"{f // (fps * 3600):02d}:{(f // (fps * 60)) % 60:02d}:{(f // fps) % 60:02d}:{f % fps:02d}"


BY = ['credit the author on screen', 'name the licence', 'state that changes were made']
SA = ['credit the author on screen', 'name the licence',
      'any adaptation of this work is released under the same licence']
LIC = {
    'pd': ('pd_expired', 'Public domain', 'public domain (published 1884)', []),
    'cc0': ('cc0', 'CC0 1.0', 'CC0 1.0 Universal public domain dedication', []),
    'by2': ('cc_by', 'CC BY 2.0', 'CC BY 2.0 Generic', BY),
    'by3': ('cc_by', 'CC BY 3.0', 'CC BY 3.0 Unported', BY),
    'by4': ('cc_by', 'CC BY 4.0', 'CC BY 4.0 International', BY),
    'bysa4': ('cc_by_sa', 'CC BY-SA 4.0', 'CC BY-SA 4.0 International', SA),
}
GW = 'Geekerwan / Wikimedia Commons (CC BY 3.0)'
CB = 'Charbax / Wikimedia Commons (CC BY 3.0)'
# record, line, licence, credit, source year, purpose, third party, carries, depicts
S = [
    ('colladon-1884', 'u011', 'pd', 'La Nature, 1884 / Wikimedia Commons (public domain)', 1884,
     "Colladon's light fountain as La Nature illustrated it in 1884: light carried inside a curved jet of water", 'none',
     'period_look', ['Colladon']),
    ('spad-pulse', 'u014', 'by4', 'Warburton et al., Scientific Reports 2017 / Wikimedia Commons (CC BY 4.0)', 2017,
     "the Heriot-Watt team's own footage: a light pulse travelling around a coil of optical fibre", 'none',
     'instrument_footage', ['Heriot Watt']),
    ('nvb-hgx', 'u055', 'by3', GW, 2024, 'NVIDIA HGX B200 boards, eight Blackwell GPUs each, shown at Computex 2024', 'none',
     'instrument_footage', ['Blackwell']),
    ('horowitz-2025', 'u068', 'bysa4', 'King of Hearts / Wikimedia Commons (CC BY-SA 4.0)', 2025,
     'Mark Horowitz speaking at Stanford in 2025', 'none', 'real_person', ['Mark Horowitz']),
    ('fiji', 'u078', 'bysa4', 'C. Spille / pcgameshardware.de / Wikimedia Commons (CC BY-SA 4.0)', 2015,
     'an AMD Fiji package: the GPU and its four HBM stacks side by side on one silicon interposer', 'none',
     'instrument_footage', ['Fiji']),
    ('hbm-p100', 'u079', 'cc0', 'Fritzchens Fritz / Wikimedia Commons (CC0)', 2022,
     "a cut through a high bandwidth memory stack beside an NVIDIA GP100: DRAM dies piled on a logic die (the photographer's labels)",
     'none', 'instrument_footage', ['high bandwidth memory']),
    ('vllm-paper', 'u089', 'by4', 'Kwon et al., arXiv 2309.06180 (CC BY 4.0)', 2023,
     "the first page of Kwon and colleagues' 2023 paper, with its figure of wasted KV cache memory", 'none',
     'instrument_footage', ['Woosuk Kwon']),
    ('dgx-gb200', 'u101', 'bysa4', 'Pokiiri / Wikimedia Commons (CC BY-SA 4.0)', 2025, 'an NVIDIA DGX GB200 rack', 'none',
     'instrument_footage', ['rack for Blackwell']),
    ('qct-gh', 'u102', 'by3', CB, 2023, 'an NVIDIA Grace Hopper module: a Grace processor beside its GPU', 'none',
     'instrument_footage', ['Grace']),
    ('altman-2019', 'u112', 'by2', 'TechCrunch / Wikimedia Commons (CC BY 2.0)', 2019,
     'Sam Altman on stage at TechCrunch Disrupt 2019', 'none', 'real_person', ['Sam Altman']),
]
STILLS = {'colladon-1884', 'horowitz-2025', 'fiji', 'hbm-p100', 'vllm-paper', 'dgx-gb200', 'altman-2019'}
VLLM = {'page': 'https://arxiv.org/abs/2309.06180', 'url': 'https://arxiv.org/pdf/2309.06180v1'}
M = json.loads((EP / 'vo/manifest.json').read_text(encoding='utf-8'))
rate = M['sampleRate']
dur = {u['id']: u['samples'] / rate for u in M['utterances']}
said = {u['id']: u['text'] for u in M['utterances']}
records, rows, hints = {}, [], {}
for i, (key, line, lk, credit, year, purpose, third, carries, depicts) in enumerate(S, 1):
    assert any(d.lower() in said[line].lower() for d in depicts), (key, line, said[line])
    still = key in STILLS
    basis, lic, ver, obl = LIC[lk]
    ident = f"arch-{i:03d}"
    rec = {"asset": f"assets/archive/{key}.{'jpg' if still else 'mp4'}", "licence": ident,
           "form": "still" if still else "clip", "aspect": "pillarbox_visible_edge", "treatment": "keep_distinct",
           "light_side": "right", "carries": carries, "depicts": depicts}
    if still:
        src = VLLM if key == 'vllm-paper' else info[key]
        sign = 1 if i % 2 else -1
        rec["still_move"] = {"pan_deg": round(sign * 1.5, 2), "zoom_from": 1.03, "zoom_to": 1.16}
        tb, fps, tin, tout, tr, asis = 30, 30.0, "00:00:00:00", tc(max(dur[line] + 0.3, 5), 30), [], True
        if key == 'vllm-paper':
            tr, asis = ["page 1 rendered from the PDF at 200 dpi"], False
    else:
        c = cuts[key]
        src = info[c['source']]
        fps = c['fps']
        rec["native_fps"] = fps
        if abs(fps - 30) > 0.05:
            rec["motion_mode"] = "retime_to_natural"
        assert c['duration'] >= dur[line] - 0.01, (key, line, dur[line], c['duration'])
        tb = round(fps)
        tin, tout = tc(c['in'], tb), tc(c['in'] + c['length'], tb)
        tr = ["trimmed to the span used"]
        if c['speed'] != 1:
            tr.append(f"slowed to {round(c['speed'] * 100)} percent speed")
        if c.get('logo_crop'):
            tr.append("cropped to remove the channel logo in the corner")
        tr.append("transcoded to H.264 without audio")
        asis = False
    records[key] = rec
    hints[line] = key
    rows.append({
        "id": ident, "provider": "arXiv" if key == 'vllm-paper' else "Wikimedia", "license": lic, "url": src['page'],
        "file": rec['asset'], "source_archive": "arXiv" if key == 'vllm-paper' else "Wikimedia Commons",
        "rights_basis": basis, "credit_line": credit,
        "retrieval_url": re.sub(r'\?.*$', '', src['url']), "retrieved_date": "2026-11-17",
        "purpose_of_use": f"archival evidence for ask-chatgpt: {purpose}",
        "third_party_rights": third if third == "none" else [third],
        "in_timecode": tin, "out_timecode": tout, "timebase": tb,
        "source_frame_rate": fps, "licence_version": ver, "obligations": obl,
        "qc_watermark": False, "derivative_transformations": tr, "uploaded_as_is": asis, "source_year": year})
(EP / 'archive.json').write_text(json.dumps(records, indent=1), encoding='utf-8')
(EP / 'assets/archive-licence.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf-8')
(EP / 'script/shots-hint.json').write_text(json.dumps(hints, indent=1), encoding='utf-8')
tot = sum(dur[l] for l in hints)
print(len(records), 'records; seconds', round(tot, 1), 'share', round(tot / sum(dur.values()), 3))
