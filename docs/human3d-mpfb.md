# 3D people with MPFB2: running it on the PC

The dressed characters are built once per machine (they are .blend files, not in git) and then used by the
storyboard renderer like before.

```powershell
# 1. assets and the MPFB2 extension (once; about 1.3 GB of downloads, kept in assets\makehuman\_downloads)
python tools\human3d_assets.py --dest assets\makehuman --install-mpfb --blender tools\blender-4.5.15-windows-x64\blender.exe

# 2. build the six roles, three variants each (about 1 minute per role), plus a lineup to look at
tools\blender-4.5.15-windows-x64\blender.exe -b --factory-startup -P tools\blender\human3d_mpfb.py -- `
    --assets assets\makehuman --out work\semmelweis-10min\human3d --variants 3 `
    --sheet work\semmelweis-10min\renders\people.png

# 3. stills of the first beats, then the 2-minute render as before
tools\blender-4.5.15-windows-x64\blender.exe -b --factory-startup -P tools\blender\storyboard_beats.py -- `
    --episode work\semmelweis-10min --beat beat-01 --beat beat-02 --beat beat-04 --beat beat-06 --still 0.5
```

Building writes absolute texture paths into the .blend files, so build on the machine that renders, and
rebuild after moving the asset folder. `--who midwife` rebuilds a single role.

What a role looks like (clothes, colours, hair, beards, age and build ranges) is the `ROLES` table at the
top of tools/blender/human3d_mpfb.py. The storyboard may pin a variant with `"variant": 2` on a cast entry;
otherwise each beat hands the variants out in turn (the first person of a role is always variant 1).

On a machine without a GPU, `STORYLOOM_CYCLES_STILLS=24` (environment variable) renders `--still` frames
with Cycles on the CPU instead of EEVEE.

Credits for the CC-BY clothing: docs/human3d-credits.md.

## How a 3D person is placed (storyboard_beats.place_human3d)

People keep their real size: a cast entry's `height` (fraction of the frame) decides how far from the camera
the person stands, not a scale factor. The feet are walked toward the camera along the floor until the
figure is that tall, but never so close that the head drops below the upper half of the frame (a high camera
looks down on anyone near it). A bust puts the head at its `screen` point at that depth, in front of any set
object on the way, with the feet on the floor. Each cast member gets a small size change (about 3 %), on top
of the role variants. The camera of the shot's last frame is used, so a camera that dollies in arrives at the
asked-for framing; when that hides the person behind the set, the first frame's camera is used instead
(`"place": "start"` on a cast entry asks for the first frame directly).
