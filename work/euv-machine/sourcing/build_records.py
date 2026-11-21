"""archive.json, the rights ledger and script/shots-hint.json for work/euv-machine.

Media come from Wikimedia Commons (the first cut of this film, sourcing/info-old.json, plus the five
fetched for this one, sourcing/info.json). Run from the repository root.
"""
import json
import re
from pathlib import Path

EP = Path('.').resolve() / 'work' / 'euv-machine'
info = json.loads((EP / 'sourcing/info-old.json').read_text(encoding='utf-8'))
info.update(json.loads((EP / 'sourcing/info.json').read_text(encoding='utf-8')))
info.update(json.loads((EP / 'sourcing/info-video.json').read_text(encoding='utf-8')))


def tc(sec, fps=30):
    f = int(round(sec * fps))
    return f"{f // (fps * 3600):02d}:{(f // (fps * 60)) % 60:02d}:{(f // fps) % 60:02d}:{f % fps:02d}"


BY = ['credit the author on screen', 'name the licence', 'state that changes were made']
SA = ['credit the author on screen', 'name the licence',
      'any adaptation of this image is released under the same licence']
LIC = {
    'pdus': ('us_federal_public_domain', 'Public domain (US government work)', 'US federal public domain', []),
    'cc0v': ('cc0', 'CC0 1.0', 'CC0 1.0 Universal public domain dedication', []),
    'pdold': ('pd_expired', 'Public domain (copyright expired)', 'Public domain, published before 1903', []),
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
    ('sun-171', 'u005', 'pdus', 'NASA Scientific Visualization Studio / SDO (public domain)', 2022,
     'the Sun filmed in extreme ultraviolet (17.1 nm) from orbit: light the atmosphere absorbs, so it barely reaches the ground', 'none', 'sun-171.mp4', 'instrument_footage'),
    ('chip-die-b', 'u008', 'cc0v', 'Fritzchens Fritz / Wikimedia Commons (CC0)', 2022, 'a processor die close up', 'none', 'chip-die-b.mp4', 'instrument_footage'),
    ('wafer-ibm', 'u007', 'by3', IBMC, 2023, 'a processed silicon wafer covered in chips', 'none', 'ibm-wafer.mp4', 'instrument_footage'),
    ('euv-tool', 'u009', 'pdus', 'Lawrence Livermore National Laboratory (public domain)', 1998,
     'an early EUV lithography research tool', 'none', 'euv-tool.jpg', 'instrument_footage'),
    ('chip-die', 'u011', 'cc0v', 'Fritzchens Fritz / Wikimedia Commons (CC0)', 2022,
     'a modern processor die under the light: billions of transistors in stacked layers', 'none', 'chip-die.mp4', 'instrument_footage'),
    ('cleanroom', 'u012', 'pdus', 'NASA Glenn Research Center (public domain)', 2004,
     'a microfabrication cleanroom, where chips are printed', 'none', 'cleanroom.jpg', 'real_place'),
    ('st-wafer', 'u013', 'by3', 'STMicroelectronics / Wikimedia Commons (CC BY 3.0)', 2022, 'a silicon wafer in an STMicroelectronics fab', 'none', 'st-wafer.mp4', 'real_place'),
    ('ucl-litho', 'u014', 'by2', 'UCL Mathematical & Physical Sciences / Wikimedia Commons (CC BY 2.0)', 2013,
     'a photolithography lab under yellow light, which does not expose the resist', 'none', 'ucl-litho.jpg', 'real_place'),
    ('ucl-scientist', 'u019', 'by3', 'UCL Mathematical & Physical Sciences / Wikimedia Commons (CC BY 3.0)', 2013,
     'a researcher at a lithography bench, coating and printing layer after layer', 'a researcher is identifiable in the frame',
     'ucl-scientist.jpg', 'real_person'),
    ('mercury-lamp', 'u040', 'pdold', 'Cooper Hewitt lamp, unknown photographer (public domain)', 1903,
     'an early mercury vapour lamp: the kind of light source early lithography used', 'none', 'mercury-lamp.jpg', 'period_look'),
    ('zeiss-otus', 'u043', 'bysa4', 'Laserlicht / Wikimedia Commons (CC BY-SA 4.0)', 2018,
     'a precision lens cut open: the glass elements that cannot work at extreme ultraviolet', 'none', 'zeiss-otus.jpg',
     'instrument_footage'),
    ('asml-lens', 'u045', 'bysa2', 'The Next Web / Wikimedia Commons (CC BY-SA 2.0)', 2006,
     'a projection lens from an ASML deep-ultraviolet lithography system', 'a person is partly in frame', 'asml-lens.jpg',
     'instrument_footage'),
    ('asml-8tower', 'u051', 'by3', 'Johfrael / Wikimedia Commons (CC BY 3.0)', 2011,
     'ASML in Veldhoven, the company that turned the experiment into a factory tool', 'none', 'asml-8tower.jpg', 'real_place'),
    ('co2-laser', 'u058', 'pdus', 'US Air Force Research Laboratory (public domain)', 2008,
     'a carbon dioxide laser: illustrative of the laser type, not the EUV driver itself', 'none', 'co2-laser.jpg',
     'instrument_footage'),
    ('laser-cut', 'u059', 'cc0v', 'Contour / Wikimedia Commons (CC0)', 2011,
     'an industrial laser at work: illustrative of high-power lasers, not the EUV driver itself', 'none', 'laser-cut.mp4', 'filmed_event'),
    ('tsmc-fab6', 'u069', 'by4', '4300streetcar / Wikimedia Commons (CC BY 4.0)', 2025,
     'a TSMC fab, where EUV machines run around the clock', 'none', 'tsmc-fab6.jpg', 'real_place'),
    ('vacuum-chamber', 'u072', 'pdus', 'NASA / James Webb Space Telescope project (public domain)', 2019,
     'a vacuum coating chamber for telescope mirrors: illustrative of optics kept in a vacuum, not an EUV tool', 'none', 'vacuum-chamber.mp4', 'instrument_footage'),
    ('soap-film', 'u078', 'bysa4', 'Pksois23 / Wikimedia Commons (CC BY-SA 4.0)', 2023,
     'thin-film interference colours on a soap bubble: the same physics as a multilayer mirror', 'none', 'soap-film.jpg',
     'filmed_event'),
    ('mirror-grind', 'u082', 'by4', 'ESO / Wikimedia Commons (CC BY 4.0)', 1994,
     'a large mirror being ground by machine: illustrative of precision optics, not an EUV mirror', 'none', 'mirror-grind.mp4', 'instrument_footage'),
    ('gold-mirror', 'u083', 'pdus', 'NASA / James Webb Space Telescope project (public domain)', 2019,
     'a coated telescope mirror segment in a cleanroom: illustrative of a precision mirror, not an EUV mirror', 'none', 'gold-mirror.mp4', 'instrument_footage'),
    ('zeiss-oberkochen', 'u084', 'bysa3', 'Johannes Geiger / Wikimedia Commons (CC BY-SA 3.0)', 2008,
     "Carl Zeiss's site in Oberkochen, southern Germany, where the mirrors are made", 'none', 'zeiss-oberkochen.jpg', 'real_place'),
    ('ibm-ray-a', 'u086', 'by3', IBMC, 2023, "IBM Research's schematic of EUV light travelling by mirrors", 'none', 'ibm-ray-a.mp4',
     'instrument_footage'),
    ('ibm-mask-a', 'u087', 'by3', IBMC, 2023, "IBM Research's schematic of a reflective mask", 'none', 'ibm-mask-a.mp4',
     'instrument_footage'),
    ('ibm-ray-c', 'u090', 'by3', IBMC, 2023, "IBM Research's schematic of the chain of mirrors from mask to wafer", 'none',
     'ibm-ray-c.mp4', 'instrument_footage'),
    ('ibm-mask-b', 'u096', 'by3', IBMC, 2023, "IBM Research's schematic of the pattern stepping across a wafer", 'none',
     'ibm-mask-b.mp4', 'instrument_footage'),
    ('st-backend', 'u101', 'by3', 'STMicroelectronics / Wikimedia Commons (CC BY 3.0)', 2022, 'automated chip-handling machines in an STMicroelectronics plant', 'none', 'st-backend.mp4', 'real_place'),
    ('raindrops', 'u106', 'by3', 'Beachfront / Wikimedia Commons (CC BY 3.0)', 2020,
     'raindrops landing at random on a puddle: the analogy for photons arriving at random', 'none', 'raindrops.mp4', 'filmed_event'),
    ('intel-d1x', 'u118', 'bysa2', 'Intel Free Press / Wikimedia Commons (CC BY-SA 2.0)', 2013,
     'construction of an Intel development fab in Oregon, where high-NA tools were assembled', 'none', 'intel-d1x.png',
     'real_place'),
    ('asml-hq', 'u119', 'cc0', 'A. Ansems / Wikimedia Commons (public domain)', 2008,
     "ASML's headquarters in Veldhoven, the Netherlands", 'none', 'asml-hq.jpg', 'real_place'),
    ('tainan-temple', 'u126', 'by4', '4300streetcar / Wikimedia Commons (CC BY 4.0)', 2025,
     'ASML machine containers arriving at a chip hub in Tainan, Taiwan', 'none', 'tainan-temple.jpg', 'real_place'),
]
M = json.loads((EP / 'vo/manifest.json').read_text(encoding='utf-8'))
rate = M['sampleRate']
dur = {u['id']: u['samples'] / rate for u in M['utterances']}
IBM_SRC = {'ibm-wafer': (84, 6.7), 'ibm-ray-a': (24, 6.5), 'ibm-ray-c': (32, 6.3), 'ibm-mask-a': (40, 5.3), 'ibm-mask-b': (44.5, 6.2)}
CUT = ["trimmed to the span used", "transcoded to H.264 without audio"]
# clip -> (source key in info, in seconds, length used, frame rate of the cut file, transformations)
VIDEO = {b: ('ibm-euv', s0, ln, 29.97, CUT) for b, (s0, ln) in IBM_SRC.items()}
VIDEO.update({
    'sun-171': ('sun-flare-171', 0, 5.9, 30.0, ["slowed to 77 percent speed", "scaled to 1080 x 1080",
                                                "transcoded to H.264 without audio"]),
    'chip-die': ('chips-cc0', 44, 8.0, 30.0, CUT), 'chip-die-b': ('chips-cc0', 112, 3.0, 30.0, CUT),
    'st-wafer': ('st-fab', 244.2, 3.4, 25.0, CUT), 'st-backend': ('st-fab', 110, 5.5, 25.0, CUT),
    'laser-cut': ('laser-cut', 0, 6.0, 30.0, CUT), 'vacuum-chamber': ('webb-coating', 20.5, 4.97, 29.97, CUT),
    'gold-mirror': ('webb-coating', 238, 6.0, 29.97, CUT), 'mirror-grind': ('mirror-grind', 0, 7.6, 25.0, CUT),
    'raindrops': ('raindrops', 5, 5.5, 23.976, CUT),
})
records, rows, hints = {}, [], {}
for i, (key, line, lk, credit, year, purpose, third, fname, carries) in enumerate(S, 1):
    base = fname.rsplit('.', 1)[0]
    clip = base in VIDEO
    src = info[VIDEO[base][0]] if clip else info[base]
    basis, lic, ver, obl = LIC[lk]
    ident = f"arch-{i:03d}"
    rec = {"asset": f"assets/archive/{fname}", "licence": ident, "form": "clip" if clip else "still",
           "aspect": "pillarbox_visible_edge", "treatment": "keep_distinct", "light_side": "right", "carries": carries}
    if clip:
        _, s0, ln, fps, tr = VIDEO[base]
        rec["native_fps"] = fps
        if abs(fps - 30) > 0.05:
            rec["motion_mode"] = "retime_to_natural"
        assert ln >= dur[line], (key, line, dur[line], ln)
        tb = round(fps)
        tin, tout, asis = tc(s0, tb), tc(s0 + ln, tb), False
    else:
        sign = 1 if i % 2 else -1
        rec["still_move"] = {"pan_deg": round(sign * 1.5, 2), "zoom_from": 1.03, "zoom_to": 1.16}
        tb = 30
        fps, tin, tout, tr, asis = 30.0, "00:00:00:00", tc(max(dur[line] + 0.3, 5)), [], True
    records[key] = rec
    hints[line] = key
    rows.append({
        "id": ident, "provider": "Wikimedia", "license": lic, "url": src['page'], "file": rec['asset'],
        "source_archive": "Wikimedia Commons", "rights_basis": basis, "credit_line": credit,
        "retrieval_url": re.sub(r'\?.*$', '', src['url']), "retrieved_date": "2026-11-16",
        "purpose_of_use": f"archival evidence for euv-machine: {purpose}",
        "third_party_rights": third if third == "none" else [third],
        "in_timecode": tin, "out_timecode": tout, "timebase": tb,
        "source_frame_rate": fps, "licence_version": ver, "obligations": obl,
        "qc_watermark": False, "derivative_transformations": tr, "uploaded_as_is": asis, "source_year": year})
(EP / 'archive.json').write_text(json.dumps(records, indent=1), encoding='utf-8')
(EP / 'assets/archive-licence.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf-8')
(EP / 'script/shots-hint.json').write_text(json.dumps(hints, indent=1), encoding='utf-8')
tot = sum(dur[l] for l in hints)
print(len(records), 'records; seconds', round(tot, 1), 'share', round(tot / sum(dur.values()), 3))
