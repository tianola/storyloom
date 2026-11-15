# Numbers computed for this project

Reproduce with: `node tools/spectrum.ts` (Node v24.21.0, computed 2026-11-06).

Model: relative Rayleigh scattering strength scales with 1/wavelength^4, normalised to red at 675 nm = 1.00.
Path length uses a flat-atmosphere secant model, 1/sin(elevation); it is an illustration, not a radiative-transfer
result, and it diverges at the horizon, so the table stops at 5 degrees.

```
violet 400 nm  scattering 8.11
blue 450 nm  scattering 5.06
green 530 nm  scattering 2.63
yellow 580 nm  scattering 1.83
orange 620 nm  scattering 1.40
red 675 nm  scattering 1.00

sun 90 degrees above the horizon  path 1.00
sun 60 degrees above the horizon  path 1.15
sun 45 degrees above the horizon  path 1.41
sun 30 degrees above the horizon  path 2.00
sun 20 degrees above the horizon  path 2.92
sun 15 degrees above the horizon  path 3.86
sun 10 degrees above the horizon  path 5.76
sun 5 degrees above the horizon  path 11.47

ratio blue/red 5.06
path 10 degrees divided by overhead 5.76
wavelength sweep 400..700 step 50
  400 nm  8.109
  450 nm  5.063
  500 nm  3.322
  550 nm  2.269
  600 nm  1.602
  650 nm  1.163
  700 nm  0.865
```
