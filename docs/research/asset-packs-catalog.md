# Asset packs catalog (CC0, unpacked under assets/)

Paths are relative to `assets/`. Counts are from directory listings. Scale numbers come from glTF accessor bounds read as JSON (Blender not used). Poly Haven props (lantern, candlestick, oil lamp, bookshelf, shelves+jars, barrels, baskets, crate, bucket, nightstands) are already wired via `assets/polyhaven`; this catalog covers what the packs add.

## 1. Packs

| Pack | Style (from preview pngs) | Fit next to chunky pixel sprites | Models |
|---|---|---|---|
| kenney/fantasy-town-kit | Flat-shaded low poly, one shared colormap, no surface detail. Orange wood, lavender stone, red/green roofs. | Best fit: plain flat colours sit well next to pixel sprites. | 167 glb (also fbx/obj) |
| kenney/retro-textures-fantasy | 117 tileable hand-painted 2D textures (plaster, brick, stone floors, planks, shuttered/lit windows, barred and wood doors, thatch/clay roofs). Not models. | Good for retexturing our own simple boxes; use nearest filtering. | 117 png |
| quaternius/medieval-village-megakit | Stylised PBR, half-timbered/plaster/brick, hand-painted with normal maps, ivy, round clay tiles. Preview is semi-realistic and lit. | Richer than the sprites. Usable if flattened (drop normal maps, high roughness) or restricted to plaster walls and doors. | 176 gltf |
| quaternius/fantasy-props-megakit | Stylised PBR props, warm and chunky (preview is a wizard library). Furniture is generic and usable; magic items are not. | Medium; same flattening advice. | 94 gltf |
| quaternius/ultimate-fantasy-rts | Toy-like low-poly RTS buildings, flat material colours (baseColorFactor, no image textures). Tiny props, designed for top-down. | Good for distant street/skyline; too small for close-ups. | about 152 gltf |
| quaternius/modular-dungeon | Flat-shaded low-poly grey stone dungeon kit (Jan 2018), FBX/OBJ only, no glTF. | Very good for the asylum cell. Needs FBX (or OBJ) import. | 41 fbx/obj |
| polyhaven | Already wired by other code. | n/a | n/a |

Licence caveat: modular-dungeon ships no licence file (see packs.json).

## 2. Scale and textures

- Kenney Fantasy Town Kit: 1 unit = 1 tile. A wall piece is 1 wide, 1 tall, 0.1 thick (wall.glb bounds y 0..1, x 0.4..0.5). Stall about 0.65 x 1.0 x 0.37, cart about 0.65 x 1.3, but lantern.glb is 1.56 tall, so props are not in tile proportion: scale per piece. Overview.html states no units (found no scale text); numbers are from bounds. Textures are external: each .glb references the relative uri `Textures/colormap.png`, so keep `GLB format/Textures/` beside the glbs.
- Quaternius Medieval Village: metres. Door_1_Flat 1.07 x 2.13 m; Wall_Plaster_Straight_L about 2 m wide, 3.1 m tall; Floor_* tiles 2 x 2 m; Prop_Wagon about 1.95 x 4.0 m. Textures external: gltf `images` uris are bare filenames (for example `T_WoodTrim_BaseColor.png`) that sit in the same `glTF/` folder as the .gltf and .bin. Keep them together.
- Quaternius Fantasy Props: metres. Bed_Twin1 1.9 wide x 2.4 long x 0.8 high; Table_Large 2.8 x 1.1 x 0.8; Chair_1 0.58 wide, 1.12 high; Bookcase_2 1.5 wide, 2.5 high; Barrel 0.7 wide, 0.9 high; Nightstand_Shelf 0.7 wide, 1.2 high; Stall_Empty 1.8 wide. Textures external: `T_Trim_Furniture_*.png`, `T_Trim_Metal_*`, `T_Trim_Props_*`, `T_Trim_Cloth_*` listed beside the gltfs in `Exports/glTF/`.
- Ultimate Fantasy RTS: scale not checked (guess: a few metres per house). No external textures; `PNG/` holds preview images only.
- Modular Dungeon: FBX/OBJ only; the .mtl uses plain Kd colours (no textures); scale not checked.

## 3. Scene need to candidate files

Folders: MV = `quaternius/medieval-village-megakit/glTF/NAME.gltf`; PROPS = `quaternius/fantasy-props-megakit/Exports/glTF/NAME.gltf`; RTS = `quaternius/ultimate-fantasy-rts/glTF/NAME.gltf`; KEN = `kenney/fantasy-town-kit/Models/GLB format/NAME.glb`; DUN = `quaternius/modular-dungeon/FBX/NAME.fbx`.

| Need | Best candidates (NAME) | Notes |
|---|---|---|
| Plastered 3-4 storey house, walls | MV: `Wall_Plaster_Straight`, `Wall_Plaster_Straight_Base`, `Wall_Plaster_Window_Wide_Flat`, `Wall_Plaster_Window_Wide_Flat2`, `Wall_Plaster_Door_Flat`, `Corner_Exterior_Wood`, `Floor_WoodDark` (storey slab), `Overhang_Plaster_Long`. KEN: `wall`, `wall-window-shutters`, `wall-door`, `wall-window-small` | Biedermeier suits flat windows: prefer `*_Flat` over `*_Round`. Avoid `Wall_Plaster_WoodGrid` (half-timber, wrong era). |
| Roofs and chimneys | MV: `Roof_RoundTiles_6x8`, `Roof_RoundTiles_8x12`, `Roof_Dormer_RoundTile`, `Prop_Chimney`, `Prop_Chimney2`. KEN: `roof-gable`, `roof-high-gable`, `chimney` | Avoid `Roof_Tower_RoundTiles`. |
| Shutters | MV: `WindowShutters_Wide_Flat_Open`, `WindowShutters_Wide_Flat_Closed`, `WindowShutters_Thin_Flat_Closed` | |
| Balcony | MV: `Balcony_Simple_Straight`, `Balcony_Simple_Corner` | Avoid `Balcony_Cross_*` (timber look). |
| Whole houses for skyline | RTS: `Houses_SecondAge_1_Level1`, `Houses_SecondAge_2_Level2`, `Houses_SecondAge_3_Level3` | Level 1-3 is upgrade tier. Avoid `Houses_FirstAge_*` (wooden huts). |
| Market stalls | PROPS: `Stall_Empty`, `Stall_Cart_Empty`. KEN: `stall`, `stall-green`, `stall-red`, `stall-bench`, `stall-stool`. RTS: `Market_SecondAge_Level1` | |
| Carts, wagons | MV: `Prop_Wagon`. KEN: `cart`, `cart-high`, `wheel` | |
| Barrels, crates, sacks, goods | PROPS: `Barrel`, `Barrel_Apples`, `Crate_Wooden`, `FarmCrate_Apple`, `FarmCrate_Carrot`, `FarmCrate_Empty`, `Bag`, `Pouch_Large`. RTS: `Crate_Stack1`, `Crate_Stack2`, `Crate_Big_Stack2`. MV: `Prop_Crate` | No basket found (Poly Haven has one). |
| Street lantern, well/pump | KEN: `lantern` (post). PROPS: `Lantern_Wall` | No well or pump found. KEN `fountain-round`, `fountain-square` are the nearest water features. |
| Fences, hedges, trees | KEN: `fence`, `fence-gate`, `hedge`, `tree`, `tree-high-round`. MV: `Prop_MetalFence_Simple`, `Prop_MetalFence_Ornament` | |
| Road and ground | KEN: `road`, `road-bend`, `road-curb`. MV: `Floor_UnevenBrick`, `Floor_Brick` | |
| General Hospital facade and court | Compose: MV plaster walls + `Prop_ExteriorBorder_Straight1`, `Overhang_Plaster_Long`, `DoorFrame_Flat_Brick`; KEN `wall-arch`, `pillar-stone`, `stairs-stone`, `stairs-wide-stone-handrail`; court: KEN `hedge`, `fountain-square`, MV `Prop_MetalFence_Ornament` | No single hospital model. Avoid RTS `Temple_*`, `TownCenter_*`. |
| Clinic doors | MV: `Door_2_Flat`, `Door_4_Flat`, `DoorFrame_Flat_WoodDark`, `Wall_Plaster_Door_Flat`. KEN: `wall-wood-door`, `wall-doorway-square` | `Door_8_*` may be double doors (guess from number). |
| His room | PROPS: `Workbench` (desk), `Table_Large`, `Chair_1`, `Stool`, `Bed_Twin1`, `Shelf_Simple`, `Scroll_1`, `Scroll_2`, `Book_Stack_1`, `Peg_Rack`, `Cabinet`, `Chest_Wood`. MV: `Floor_WoodDark` | Poly Haven already has bookshelf, candle. |
| First Clinic ward | PROPS: `Bed_Twin1`, `Bed_Twin2` (wooden; no iron bed exists), `Nightstand_Shelf`, `Cabinet`, `Bench`, `Table_Large` (register table), `Bucket_Metal`, `Pot_1`, `Mug`. MV: `Floor_WoodLight`, `Floor_Brick` | No crucifix, wash stand, basin or jug found: use `Bucket_Metal` / `Pot_1` / `Vase_2` stand-ins or build from boxes. Avoid `Chandelier`, `Torch_Metal`. |
| Dissecting room | PROPS: `Workbench`, `Workbench_Drawers`, `Table_Large`, `Shelf_Small_Bottles`, `SmallBottles_1`, `Bottle_1`, `Table_Knife`, `Bucket_Metal`. DUN: `Bones`, `Bones2` (guess: skeleton, per preview) | Avoid `Potion_*`, `Cauldron`, `Chalice`, `Dummy`, `Anvil`, weapons. |
| Asylum cell | DUN: `ModularStoneWall`, `ModularStoneWall_top`, `ModularFloor`, `Window` (barred in preview), `Bars`, `Entrance`, `Entrance2`, `Rock1`..`Rock5`, `Barrel`. PROPS: `Stool`, `Bucket_Wooden_1`, `Chain_Coil`, `Rope_1`, `Bench`. Gate: MV `Prop_MetalFence_Simple`, DUN `Bars`, PROPS `Lantern_Wall` | No straw model found; paint a plane with `kenney/retro-textures-fantasy/PNG/roof_thatch_center.png`. Avoid `Candelabrum*`, `Chest_gold`, `Carpet`, `Torch*`, `Column*`. |
| Retexturing simple boxes | `kenney/retro-textures-fantasy/PNG/`: `floor_wood_planks.png`, `floor_stone.png`, `floor_stone_pattern.png`, `floor_tiles_tan_large.png`, `door_wood.png`, `door_metal_gate.png`, `door_wood_window_lit.png`, `roof_clay_red_center.png`, `floor_ground_dirt.png` | Plaster and brick wall tiles are in the preview (top rows); their filenames are not in my alphabetical listing (I saw only the `d`..`r` names above), so `ls PNG/` before wiring. |

Avoid across packs (fantasy or out of period): all towers (`WatchTower_*`, `WallTowers_*`, `TowerHouse_*`, `Roof_Tower_RoundTiles`), castle, temple, wonder, barracks, archery, mine, dock buildings, wizard and loot props (`Cauldron`, `Potion*`, `Chalice`, `Coin*`, `Chest_gold`, `Candelabrum*`), weapons and `WeaponStand`, `Dummy`, `Banner_*`.

## 4. Top 15 to wire first (what the packs add beyond Poly Haven)

1. `quaternius/medieval-village-megakit/glTF/Wall_Plaster_Straight.gltf` - vienna facade
2. `quaternius/medieval-village-megakit/glTF/Wall_Plaster_Window_Wide_Flat.gltf` - vienna windows
3. `quaternius/medieval-village-megakit/glTF/Wall_Plaster_Door_Flat.gltf` - vienna / clinic doors
4. `quaternius/medieval-village-megakit/glTF/Roof_RoundTiles_6x8.gltf` - vienna roofs
5. `quaternius/medieval-village-megakit/glTF/WindowShutters_Wide_Flat_Open.gltf` - vienna shutters
6. `quaternius/medieval-village-megakit/glTF/Prop_Wagon.gltf` - vienna cart
7. `quaternius/fantasy-props-megakit/Exports/glTF/Stall_Empty.gltf` - market
8. `quaternius/fantasy-props-megakit/Exports/glTF/FarmCrate_Apple.gltf` - market goods
9. `kenney/fantasy-town-kit/Models/GLB format/lantern.glb` - street (check scale)
10. `quaternius/medieval-village-megakit/glTF/Prop_MetalFence_Ornament.gltf` - hospital court, asylum gate
11. `quaternius/fantasy-props-megakit/Exports/glTF/Bed_Twin1.gltf` - ward, his room
12. `quaternius/fantasy-props-megakit/Exports/glTF/Table_Large.gltf` - register / dissecting table
13. `quaternius/fantasy-props-megakit/Exports/glTF/Workbench_Drawers.gltf` - his desk, dissecting room
14. `quaternius/modular-dungeon/FBX/ModularStoneWall.fbx` (with `ModularFloor.fbx`, `Window.fbx`) - asylum cell; FBX only
15. `quaternius/medieval-village-megakit/glTF/Floor_WoodDark.gltf` - interior floors, storey slabs

Next tier: `Stool`, `Chair_1`, `Bucket_Metal`, `Chain_Coil`, DUN `Bars`, KEN `tree`, `road`, `stairs-stone`.

## Cautions

- glTF files have separate `.bin` and png siblings: reference them in place, do not move a lone .gltf.
- Kenney glb needs `Textures/colormap.png` relative to the glb; do not flatten the folder.
- Guessed from names or previews, not verified: `Door_8_*`, `Bones*.fbx` content, dungeon `Window` bars, RTS and dungeon scale.
