import json
from pathlib import Path

EP = Path('.').resolve() / 'work' / 'the-light-machine'
info = json.loads((EP / 'sourcing/info.json').read_text(encoding='utf-8'))


def tc(sec, fps=30):
    f = int(round(sec * fps))
    return f"{f // (fps * 3600):02d}:{(f // (fps * 60)) % 60:02d}:{(f // fps) % 60:02d}:{f % fps:02d}"


BY = ['credit the author on screen', 'name the licence', 'state that changes were made']
SA = ['credit the author on screen', 'name the licence',
      'any adaptation of this image is released under the same licence']
LIC = {
    'pdus': ('us_federal_public_domain', 'Public domain (US government work)', 'US federal public domain', []),
    'cc0': ('cc0', 'Public domain, released by the author', 'Author release to the public domain', []),
    'by2': ('cc_by', 'CC BY 2.0', 'CC BY 2.0 Generic', BY),
    'by3': ('cc_by', 'CC BY 3.0', 'CC BY 3.0 Unported', BY),
    'by4': ('cc_by', 'CC BY 4.0', 'CC BY 4.0 International', BY),
    'bysa2': ('cc_by_sa', 'CC BY-SA 2.0', 'CC BY-SA 2.0 Generic', SA),
    'bysa3': ('cc_by_sa', 'CC BY-SA 3.0', 'CC BY-SA 3.0 Unported', SA),
    'bysa4': ('cc_by_sa', 'CC BY-SA 4.0', 'CC BY-SA 4.0 International', SA),
}
IBMC = 'IBM Research / Wikimedia Commons (CC BY 3.0)'
# key, line, licence, credit, source year, purpose, third party, file, carries
S = [
    ('euv-tool', 'u006', 'pdus', 'Lawrence Livermore National Laboratory (public domain)', 1998, 'an EUV lithography research tool, the kind of machine this film is about', 'none', 'euv-tool.jpg', 'instrument_footage'),
    ('cleanroom', 'u009', 'pdus', 'NASA Glenn Research Center (public domain)', 2004, 'a microfabrication cleanroom, where chips are drawn', 'none', 'cleanroom.jpg', 'real_place'),
    ('wafer-ibm', 'u010', 'by3', IBMC, 2023, 'a processed silicon wafer', 'none', 'ibm-wafer.mp4', 'instrument_footage'),
    ('ucl-litho', 'u012', 'by2', 'UCL Mathematical & Physical Sciences / Wikimedia Commons (CC BY 2.0)', 2013, 'a photolithography lab: light shone through a mask onto coated wafers', 'none', 'ucl-litho.jpg', 'real_place'),
    ('ucl-scientist', 'u021', 'by3', 'UCL Mathematical & Physical Sciences / Wikimedia Commons (CC BY 3.0)', 2013, 'a researcher in a lithography cleanroom: laboratory work before it reaches a factory', 'a researcher is identifiable in the frame', 'ucl-scientist.jpg', 'real_person'),
    ('asml-hq', 'u023', 'cc0', 'A. Ansems / Wikimedia Commons (public domain)', 2008, "ASML's headquarters in Veldhoven, the company at the centre of the story", 'none', 'asml-hq.jpg', 'real_place'),
    ('asml-lens', 'u026', 'bysa2', 'The Next Web / Wikimedia Commons (CC BY-SA 2.0)', 2006, 'a projection lens from an ASML lithography system', 'a person is partly in frame', 'asml-lens.jpg', 'instrument_footage'),
    ('tsmc-fab6', 'u028', 'by4', '4300streetcar / Wikimedia Commons (CC BY 4.0)', 2025, 'a TSMC fab, one of the customers that paid for the machine', 'none', 'tsmc-fab6.jpg', 'real_place'),
    ('trumpf-disk', 'u042', 'bysa3', 'TRUMPF / Wikimedia Commons (CC BY-SA 3.0)', 2006, "a TRUMPF industrial disk laser: illustrative of the maker's laser work, not the EUV driver itself", 'none', 'trumpf-disk.jpg', 'instrument_footage'),
    ('co2-laser', 'u044', 'pdus', 'US Air Force Research Laboratory (public domain)', 2008, 'a carbon dioxide laser: illustrative of the laser type, not the EUV driver itself', 'none', 'co2-laser.jpg', 'instrument_footage'),
    ('ibm-ray-a', 'u048', 'by3', IBMC, 2023, "IBM Research's schematic of EUV light travelling by mirrors", 'none', 'ibm-ray-a.mp4', 'instrument_footage'),
    ('webb-primary', 'u049', 'pdus', 'NASA / MSFC / D. Higginbotham (public domain)', 2011, "a space telescope's primary mirror: illustrative of a large precision mirror, not an EUV mirror", 'none', 'webb-primary.jpg', 'instrument_footage'),
    ('ibm-ray-b', 'u052', 'by3', IBMC, 2023, "IBM Research's schematic of light reflecting along a chain of mirrors", 'none', 'ibm-ray-b.mp4', 'instrument_footage'),
    ('ibm-mask-a', 'u054', 'by3', IBMC, 2023, "IBM Research's schematic of a reflective mask over a wafer", 'none', 'ibm-mask-a.mp4', 'instrument_footage'),
    ('ibm-mask-b', 'u056', 'by3', IBMC, 2023, "IBM Research's schematic of the pattern stepping across a wafer", 'none', 'ibm-mask-b.mp4', 'instrument_footage'),
    ('ibm-ray-c', 'u058', 'by3', IBMC, 2023, "IBM Research's schematic of the chain of mirrors from source to wafer", 'none', 'ibm-ray-c.mp4', 'instrument_footage'),
    ('hubble-polish', 'u059', 'pdus', 'NASA Marshall Space Flight Center (public domain)', 1979, 'a large telescope mirror being polished: illustrative of precision mirror polishing, not an EUV mirror', 'none', 'hubble-polish.jpg', 'instrument_footage'),
    ('zeiss-oberkochen', 'u061', 'bysa3', 'Johannes Geiger / Wikimedia Commons (CC BY-SA 3.0)', 2008, "Carl Zeiss's site in Oberkochen, where the optics company works", 'none', 'zeiss-oberkochen.jpg', 'real_place'),
    ('zeiss-otus', 'u062', 'bysa4', 'Laserlicht / Wikimedia Commons (CC BY-SA 4.0)', 2018, 'a Zeiss precision lens cut open: illustrative of Zeiss optics, not an EUV mirror', 'none', 'zeiss-otus.jpg', 'instrument_footage'),
    ('tainan-1', 'u069', 'by4', '4300streetcar / Wikimedia Commons (CC BY 4.0)', 2025, 'ASML air freight containers in Tainan: the one supplier delivering to a chip hub', 'none', 'tainan-1.jpg', 'real_place'),
    ('tainan-temple', 'u070', 'by4', '4300streetcar / Wikimedia Commons (CC BY 4.0)', 2025, 'ASML containers beside a temple in Tainan: one supplier, delivering worldwide', 'none', 'tainan-temple.jpg', 'real_place'),
    ('intel-d1x', 'u074', 'bysa2', 'Intel Free Press / Wikimedia Commons (CC BY-SA 2.0)', 2013, 'construction of an Intel development fab, where high-NA tools were assembled', 'none', 'intel-d1x.png', 'real_place'),
    ('wafer12', 'u089', 'bysa3', 'Peellden / Wikimedia Commons (CC BY-SA 3.0)', 2008, 'a twelve-inch silicon wafer, the material inside a phone', 'none', 'wafer12.jpg', 'instrument_footage'),
    ('asml-8tower', 'u091', 'by3', 'Johfrael / Wikimedia Commons (CC BY 3.0)', 2011, 'an ASML building: the company most people have never heard of', 'none', 'asml-8tower.jpg', 'real_place'),
    ('wafer-researcher', 'u092', 'pdus', 'US Department of Energy (public domain)', 2013, 'a silicon wafer being inspected, the quiet end of the story', 'none', 'wafer-researcher.jpg', 'real_person'),
]
M = json.loads((EP / 'vo/manifest.json').read_text(encoding='utf-8'))
rate = M['sampleRate']
dur = {u['id']: (u['endSample'] - u['startSample']) / rate for u in M['utterances']}
IBM_SRC = {'ibm-wafer': (84, 6.7), 'ibm-ray-a': (24, 4.8), 'ibm-ray-b': (28, 4.6), 'ibm-ray-c': (32, 6.3),
           'ibm-mask-a': (40, 5.3), 'ibm-mask-b': (44.5, 6.2)}
records, rows, hints = {}, [], {}
for i, (key, line, lk, credit, year, purpose, third, fname, carries) in enumerate(S, 1):
    base = fname.rsplit('.', 1)[0]
    ibm = base in IBM_SRC
    src = info['ibm-euv'] if ibm else info[base]
    basis, lic, ver, obl = LIC[lk]
    ident = f"arch-{i:03d}"
    rec = {"asset": f"assets/archive/{fname}", "licence": ident, "form": "clip" if ibm else "still",
           "aspect": "pillarbox_visible_edge", "treatment": "keep_distinct", "light_side": "right",
           "carries": carries}
    if ibm:
        rec["native_fps"] = 29.97
    else:
        sign = 1 if i % 2 else -1
        rec["still_move"] = {"pan_deg": round(sign * 1.5, 2), "zoom_from": 1.03, "zoom_to": 1.16}
    records[key] = rec
    hints[line] = key
    if ibm:
        s0, ln = IBM_SRC[base]
        tin, tout = tc(s0), tc(s0 + ln)
        tr, asis = ["trimmed to the span used", "transcoded to H.264 without audio"], False
    else:
        tin, tout = "00:00:00:00", tc(max(dur[line] + 0.3, 5))
        tr, asis = [], True
    rows.append({
        "id": ident, "provider": "Wikimedia", "license": lic, "url": src['page'], "file": rec['asset'],
        "source_archive": "Wikimedia Commons", "rights_basis": basis, "credit_line": credit,
        "retrieval_url": src['url'], "retrieved_date": "2026-11-16",
        "purpose_of_use": f"archival evidence for the-light-machine: {purpose}",
        "third_party_rights": third if third == "none" else [third],
        "in_timecode": tin, "out_timecode": tout, "timebase": 30,
        "source_frame_rate": 29.97 if ibm else 30.0, "licence_version": ver, "obligations": obl,
        "qc_watermark": False, "derivative_transformations": tr, "uploaded_as_is": asis, "source_year": year})
(EP / 'archive.json').write_text(json.dumps(records, indent=1), encoding='utf-8')
(EP / 'assets/archive-licence.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf-8')
(EP / 'script/shots-hint.json').write_text(json.dumps(hints, indent=1), encoding='utf-8')
tot = sum(dur[l] for l in hints)
print(len(records), 'records; seconds', round(tot, 1), 'share', round(tot / sum(dur.values()), 3))
