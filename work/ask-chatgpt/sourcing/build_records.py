"""archive.json, the rights ledger and script/shots-hint.json for work/ask-chatgpt.

Clips were cut by sourcing/cut.py from Wikimedia Commons transcodes (sourcing/cuts.json records the in point,
length and speed of each); stills were fetched by sourcing/stills.py. Run from the repository root.
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
    'cc0': ('cc0', 'CC0 1.0', 'CC0 1.0 Universal public domain dedication', []),
    'by3': ('cc_by', 'CC BY 3.0', 'CC BY 3.0 Unported', BY),
    'by4': ('cc_by', 'CC BY 4.0', 'CC BY 4.0 International', BY),
    'bysa3': ('cc_by_sa', 'CC BY-SA 3.0', 'CC BY-SA 3.0 Unported', SA),
    'bysa4': ('cc_by_sa', 'CC BY-SA 4.0', 'CC BY-SA 4.0 International', SA),
}
LS = 'Lawrence Systems / Wikimedia Commons (CC BY 3.0)'
GW = 'Geekerwan / Wikimedia Commons (CC BY 3.0)'
CB = 'Charbax / Wikimedia Commons (CC BY 3.0)'
JB = 'Jan Beránek / Wikimedia Commons (CC BY-SA 4.0)'
SPAD = 'Warburton et al., Scientific Reports 2017 / Wikimedia Commons (CC BY 4.0)'
# record, line, licence, credit, source year, purpose, third party, carries
S = [
    ('typing', 'u001', 'by4', 'C40115 / Wikimedia Commons (CC BY 4.0)', 2026, 'someone typing a question on a laptop', 'none', 'filmed_event'),
    ('dc-cables', 'u003', 'by3', LS, 2024, 'network cabling in a working data centre: the glass and copper a request travels through', 'none', 'real_place'),
    ('dc-rows', 'u004', 'by3', LS, 2024, 'a data hall: rows of server cabinets', 'a technician is visible far down the aisle', 'real_place'),
    ('dc-chillers', 'u009', 'by3', LS, 2024, "a data centre's chiller plant, the cooling machinery every hall depends on", 'none', 'real_place'),
    ('typing-b', 'u013', 'by4', 'C40115 / Wikimedia Commons (CC BY 4.0)', 2026, 'typing: one of billions of prompts a day', 'none', 'filmed_event'),
    ('cell-tower', 'u014', 'cc0', 'Wikideas1 / Wikimedia Commons (CC0)', 2023, 'a mobile phone mast, the first hop of a request', 'none', 'real_place'),
    ('dc-fiber2', 'u015', 'by3', LS, 2024, 'bundles of optical fibre in a data centre', 'none', 'real_place'),
    ('laser-water', 'u016', 'bysa3', 'engineerguy (Bill Hammack, Nick Ziech, Patrick Ryan) / Wikimedia Commons (CC BY-SA 3.0)', 2011,
     'a laser beam trapped inside a falling stream of water by total internal reflection, the principle of optical fibre', 'none', 'filmed_event'),
    ('spad-pulse', 'u017', 'by4', SPAD, 2017, 'a light pulse filmed travelling through a coiled optical fibre, a few nanoseconds per loop', 'none', 'instrument_footage'),
    ('dc-hall', 'u020', 'by3', LS, 2024, 'a large data hall seen from below the cable trays: illustrative of a data centre, not the Abilene site', 'none', 'real_place'),
    ('nvb-hgx', 'u021', 'by3', GW, 2024, 'NVIDIA HGX B200 boards, eight Blackwell GPUs each, shown at Computex 2024', 'none', 'instrument_footage'),
    ('gh-server', 'u022', 'by3', CB, 2023, 'an NVIDIA Grace-based server opened up at Computex 2023: illustrative of the machines a request is handed to', 'none', 'instrument_footage'),
    ('nvb-tray', 'u065', 'by3', GW, 2024, 'a Blackwell GPU package on a GB200 compute board, close up', 'none', 'instrument_footage'),
    ('qct-gh', 'u079', 'by3', CB, 2023, 'an NVIDIA Grace Hopper module: the GPU die is flanked by its stacks of high bandwidth memory (the previous generation)', 'none', 'instrument_footage'),
    ('hbm-p100', 'u080', 'cc0', 'Fritzchens Fritz / Wikimedia Commons (CC0)', 2022,
     "a cut through an HBM stack beside an NVIDIA GP100: DRAM dies piled on a logic die, on a silicon interposer (the photographer's labels)", 'none', 'instrument_footage'),
    ('fiji', 'u083', 'bysa4', 'C. Spille / pcgameshardware.de / Wikimedia Commons (CC BY-SA 4.0)', 2015,
     'an AMD Fiji package: a GPU and four HBM stacks side by side on one silicon interposer', 'none', 'instrument_footage'),
    ('dgx-gb200', 'u102', 'bysa4', 'Pokiiri / Wikimedia Commons (CC BY-SA 4.0)', 2025, 'an NVIDIA DGX GB200 rack', 'none', 'instrument_footage'),
    ('smuc-racks', 'u111', 'by3', 'IBM Research / Wikimedia Commons (CC BY 3.0)', 2012, 'the front of supercomputer racks, status lights through the mesh doors', 'none', 'real_place'),
    ('nvb-server', 'u113', 'by3', GW, 2024, 'a liquid-cooled GPU server: cold plates and coolant lines on the processors', 'none', 'instrument_footage'),
    ('smuc-anim', 'u114', 'by3', 'IBM Research / Wikimedia Commons (CC BY 3.0)', 2012,
     "IBM's animation of a water-cooled cold plate on a processor: illustrative of direct liquid cooling", 'none', 'instrument_footage'),
    ('dc-pumps', 'u115', 'by3', LS, 2024, "a data centre's pump room, moving the cooling water", 'none', 'real_place'),
    ('tower-showers', 'u116', 'bysa4', JB, 2019, 'water raining down inside a cooling tower (a power station tower: illustrative of evaporative cooling)', 'none', 'real_place'),
    ('tower-inside', 'u117', 'bysa4', JB, 2019, 'looking up inside a cooling tower as vapour rises out of the top (illustrative of evaporative cooling)', 'none', 'real_place'),
    ('dc-roof', 'u118', 'by3', LS, 2024, "a data centre's rooftop heat rejection units", 'none', 'real_place'),
    ('dc-chillers2', 'u128', 'by3', LS, 2024, 'the chiller plant of a large data centre', 'none', 'real_place'),
    ('spad-b', 'u130', 'by4', SPAD, 2017, 'the light pulse again, travelling through the coiled fibre', 'none', 'instrument_footage'),
    ('dc-fiber', 'u131', 'by3', LS, 2024, 'optical fibre patched into network equipment', 'none', 'real_place'),
]
STILLS = {'hbm-p100', 'fiji', 'dgx-gb200'}
M = json.loads((EP / 'vo/manifest.json').read_text(encoding='utf-8'))
rate = M['sampleRate']
dur = {u['id']: u['samples'] / rate for u in M['utterances']}
records, rows, hints = {}, [], {}
for i, (key, line, lk, credit, year, purpose, third, carries) in enumerate(S, 1):
    still = key in STILLS
    basis, lic, ver, obl = LIC[lk]
    ident = f"arch-{i:03d}"
    rec = {"asset": f"assets/archive/{key}.{'jpg' if still else 'mp4'}", "licence": ident,
           "form": "still" if still else "clip", "aspect": "pillarbox_visible_edge", "treatment": "keep_distinct",
           "light_side": "right", "carries": carries}
    if still:
        src = info[key]
        sign = 1 if i % 2 else -1
        rec["still_move"] = {"pan_deg": round(sign * 1.5, 2), "zoom_from": 1.03, "zoom_to": 1.16}
        tb, fps, tin, tout, tr, asis = 30, 30.0, "00:00:00:00", tc(max(dur[line] + 0.3, 5), 30), [], True
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
        "id": ident, "provider": "Wikimedia", "license": lic, "url": src['page'], "file": rec['asset'],
        "source_archive": "Wikimedia Commons", "rights_basis": basis, "credit_line": credit,
        "retrieval_url": re.sub(r'\?.*$', '', src['url']), "retrieved_date": "2026-11-16",
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
