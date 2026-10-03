# Saltmoss Harbor — design & production spec

A cozy fishing life-sim demo in a hyper-real **claymation** style. You are **Pip**, a young puffin who inherits Gran's
crab boat (*The Sally Mae*) and her shuttered fish shop (*The Salty Puffin*) in Saltmoss Harbor, a rickety, sea-worn
fishing town on stilts at the edge of the cold Grey Sea. Sail out, drop crab pots, line-fish, dredge the deep for
treasures, ride out storms, then sell your catch over the counter and fill the town museum. Bring the harbor back to
life.

Decisions (from the brief): cast of sea critters · stepped 12 fps world with a smooth camera (settings toggle for
full-film mode) · cozy with drama: storms are exciting and make things harder, nothing is ever lost for good.

Engine: Unity 6000.3.20f1, URP (Forward+), Mono, macOS (universal) · Windows x64 · Linux x64. Licensed builds run
on the LAN VM `kiki-unity` via `Tools/remote.sh` (the Mac has no Unity license).

---

## 1. Look: "hyper-real claymation"

The target is a photographed stop-motion tabletop set, not a cartoon render.

| Element | How |
|---|---|
| Forms | Soft, chunky, slightly lumpy hand-pressed shapes. Built from signed-distance primitives with smooth unions, then hand-imperfection: low-frequency lumps, thumb dents, slightly uneven symmetry. Separate coloured pieces of clay pressed together (visible seams), as real puppets are built. |
| Surface | `Saltmoss/Clay` shader: triplanar fingerprint + tool-scrape detail normals in rest-pose object space (stick to skinned surfaces), subtle albedo mottling + specks, broad soft specular (plasticine sheen), wrap-lit subsurface warmth at the terminator, per-vertex gloss (eyes and varnished bits are glossy). |
| Boil | Every animated step re-seeds a tiny vertex displacement (≈0.4 mm at puppet scale) so surfaces "crawl" like re-handled clay. |
| Motion | `ClayClock` steps the world at 12 fps ("on twos"). Characters, the boat's visual hull, waves, gulls, smoke, rain and particles only change pose on a step. Gameplay and the camera stay at full rate; **Full-film mode** also steps the camera. Settings: Stop-motion = Twos (12) / Ones (24) / Off (smooth, motion-sensitivity). |
| Set dressing | Cotton-wool clouds, chimney smoke and spray; a painted, curved sky backdrop; sculpted clay sea with glossy varnish and white clay foam; glass-bead rain. |
| Camera | Long-ish lens (30–35° vfov), slightly high angle, shallow depth of field auto-focused on the subject (tabletop miniature), SSAO, soft key + fill + rim, film grain, gentle vignette, warm grade, ±1.5 % per-step exposure flicker (lights on a real stage). |

Scale: 1 unit = 1 m. Critters are 0.6–1.6 m tall so physics/controls feel normal; DOF and lens sell the miniature.

## 2. Cast

| id | Who | Species | Height | Voice (blips) |
|---|---|---|---|---|
| `pip` | You. Young puffin skipper. Yellow sou'wester, red knitted scarf, orange feet. | Atlantic puffin | 0.9 m | bright, 340 Hz, quick |
| `walter` | Harbormaster. Gruff, kind. Navy peacoat with brass buttons, captain's cap, huge mustache, tusks. Sells boat upgrades, forecasts weather. | Walrus | 1.6 m | low growl, 105 Hz, slow |
| `nell` | Runs the counter of The Salty Puffin with you. Striped apron, red bandana. Chowder recipes, shop tips. | Sea otter | 1.15 m | warm, 250 Hz |
| `marge` | Postmistress. Post cap, round glasses, mail satchel, big pouch beak. Special orders by letter. | Pelican | 1.4 m | nasal honk, 290 Hz |
| `inkwell` | Professor, curator of the Tidewrack Museum (inside a giant upturned hull). Monocle, bow tie, tweed waistcoat. | Octopus | 1.3 m | wobbly, bubbly, 165 Hz |
| `shelby` | Kid. Too-big whelk shell covered in stickers, eyestalks, one big claw. Loves sea glass. | Hermit crab | 0.6 m | squeaky, 470 Hz, fast |
| customers | Gulls, crabs, seals in hats/scarves with colour variants. | — | 0.5–1.1 m | species blips |

## 3. Loop

1. **Morning in town** — talk to townsfolk, read Marge's letters (special orders), check Walter's forecast board.
2. **Sail out** on *The Sally Mae*. Grounds get rougher and richer with distance:
   - **The Shallows** (0–160 m from the harbor mouth): calm; herring, mackerel, flounder, smelt, cod; dungeness crab.
   - **Kelp Reach** (160–380 m): kelp forests, rain squalls; salmon, rockfish, lingcod, halibut, wolf eel; snow crab.
   - **The Grey Deep** (380–750 m): swell, storms, icing, icebergs, the wreck; sablefish, lumpsucker, ratfish, anglerfish, oarfish (legendary), ocean sunfish (rare); red & golden king crab.
   - Fog bank beyond 780 m ("Too thick out there, Pip — turn her around").
3. **At sea**:
   - **Crab pots**: drop a buoyed pot (boat slow); pots fill while you do other things (also overnight). Haul with the winch: keep the tension needle in the green as the boat heaves; storms make the band jump. The pot swings aboard, crabs tumble onto the deck; little ones are tossed back automatically ("Good steward!").
   - **Line fishing**: cast at fish shadows, wait through nibbles, hook on the bite (Animal Crossing timing), big fish add a short reel-tension bar.
   - **Dredging**: sonar pings / glimmering water mark treasure. Lower the dredge to the pinged depth, crank it up: treasure, sea glass or junk (boot, tin can, tangled net — Nell pays a sand dollar per bit of junk to keep the sea clean).
   - **Weather drama**: rogue waves are telegraphed — take them bow-first or the engine sputters and pots tangle. In the Grey Deep ice builds on deck and slows the boat: knock it off with the mallet. Nothing is lost for good.
4. **Home**: tie up at the dock; the crane swings the catch into the shop's cold store.
5. **The Salty Puffin**: open the counter; customers queue with speech-bubble requests; serve from the ice display. Coins are **sand dollars**. Tips for exact matches and fresh catch.
6. **Spend**: Walter's yard (pot count, hold size, winch, hull, deck lights, sonar) and shop upgrades (bigger display, ice, new sign and paint, lanterns, bunting). Upgrades are visible in the world.
7. **Museum**: donate treasures and first-of-a-kind fish to Professor Inkwell (collection book with silhouettes for undiscovered entries).
8. **Evening/night**: lanterns, lit windows, a buoy bell. Sleep at home to save and start a new day. Days are 12 real minutes (06:00–24:00).

Harbor restoration (demo arc): three tiers driven by sales, donations and upgrades — each tier visibly changes the town
(lit lanterns, fresh paint, bunting, more customers, the lighthouse relit) and ends with a little ceremony on the pier.

## 4. Dialogue

- Clay-slab dialogue box with a **live portrait bust**: the speaking character's own clay model on an offscreen
  portrait stage, lit like a studio, changing **expressions** (neutral, happy, laugh, surprised, sad, worried, angry,
  smug, thinking, sleepy, determined) by replacement mouths, eyelids and brow poses — exactly how stop-motion faces work.
- **Typewriter** text crawl with punctuation pauses, inline tags: `[happy]` expression, `{p}` pause, `{w}…{/w}` wavy,
  `{s}…{/s}` shaky, `{b}…{/b}` bold, `{c=#hex}…{/c}` colour, `{spd=0.5}` speed. Hold to fast-forward, press to finish/advance.
- **Voice blips (Animalese-style)**: each letter plays a short synthesized formant syllable at the character's pitch
  (vowel letters → their vowel, consonants → noise/nasal onset into the letter-name vowel), with per-character timbre
  (growl, honk, bubbles) and an intonation contour (questions rise, exclamations punch). **Mumble/gibberish VO**:
  longer multi-syllable greetings and reactions ("Hrrm-hmm!") on approach and on big beats.
- Choices (2–3 options) branch the script. Scripts live in `Game/Assets/Saltmoss/Dialogue/*.txt`.

## 5. Asset contract

### 5.1 Coordinates & units
Unity convention everywhere (Python tools too): **x right, y up, z forward**, metres, left-handed. Characters face
+Z with feet at the origin. Props: pivot bottom-centre. Fish: centred, head toward +Z. Treasures: bottom-centre.

### 5.2 `.claymesh` (binary, little-endian) — written by `Tools/clay`, imported by `ClayMeshImporter`
```
char[4] "CLAY"; u32 version = 2
u32 boneCount
  per bone:  str name; i32 parent (-1 root); f32[3] restPos (model space; rest rotations are identity)
u32 pieceCount
  per piece: str name; u8 matClass; u8 flags (1 = hidden by default, 2 = skinned); i32 rigidBone (-1 none)
             u32 vertexCount; u32 indexCount
             f32[3*vc] positions (model space)   f32[3*vc] normals   u8[4*vc] rgba
             if skinned: u8[4*vc] boneIndex; f32[4*vc] boneWeight (sum to 1)
             u32[ic] triangle indices
u32 socketCount
  per socket: str name; i32 bone (-1 root); f32[3] pos (model space); f32[4] rot (quat xyzw)
str = u16 byteLength + UTF-8
```
- `rgba`: RGB = clay albedo (sRGB) with baked mottling/AO; **A = gloss** (0 matte clay … 255 wet/varnished/eyes).
- `matClass`: 0 clay · 1 emissive (lantern glass, windows; glows at night) · 2 cotton (wool smoke/cloud) · 3 sea-foam clay · 4 cutout net.
- Rigid pieces are parented to `rigidBone` (or the root). Skinned pieces use up to 4 weights.
- Expression replacement pieces are `hidden by default` and named by role (see 5.3).

### 5.3 Character rig (bones; omit what a species doesn't have)
`root` (feet, origin) › `hips` › `spine` › `chest` › `neck` › `head` › {`jaw`, `eye_L`, `eye_R`, `pupil_L`, `pupil_R`,
`brow_L`, `brow_R`, `mouth`, `hat`} · `chest` › `arm_L` › `elbow_L` › `hand_L` (same `_R`) · `hips` › `leg_L` › `knee_L`
› `foot_L` (same `_R`) · `hips` › `tail` › `tail2`. Extras: `stache` (walter), `pouch` (marge), `tent{0-7}_{0-3}`
(inkwell), `stalk_L/_R` + `shell` + `claw_R` (shelby). Sockets: `prop_R` (hand-held items), `bust` (portrait camera
target, centre of face), `talk` (speech bubble anchor).
Face pieces (rigid to the named bone): `pupil_L/_R` → `pupil_*`; `brow_L/_R` → `brow_*`; replacement pieces under
`mouth`/`jaw`: `mouth_neutral` (visible), `mouth_smile`, `mouth_open`, `mouth_o`, `mouth_frown`, `mouth_grin`,
`mouth_wavy`; eyelids `lidhalf_L/_R`, `lidclosed_L/_R`, happy-arc eyes `eyehappy_L/_R`, cheeks `blush_L/_R` (all hidden).

### 5.4 Model list (`Game/Assets/Saltmoss/Models/<group>/<id>.claymesh`)
- `chars/`: pip, walter, nell, marge, inkwell, shelby, cust_gull, cust_crab, cust_seal (+ hat pieces `hat_*` hidden for variants)
- `boat/`: sally_mae (sockets: `helm`, `rail_cast`, `winch`, `boom_tip`, `pot_slot_0..5`, `smoke`, `deck_light_*`, `hold`), crab_pot, buoy, dredge, mallet, rod
- `fish/` (16): herring, mackerel, flounder, smelt, cod, salmon, rockfish, lingcod, halibut, wolf_eel, sablefish, lumpsucker, ratfish, anglerfish, oarfish, sunfish
- `crabs/` (5): dungeness, snow_crab, red_king, golden_king, sea_urchin
- `treasure/` (20): sea_glass, message_bottle, ship_bell, brass_compass, pearl, gold_doubloon, pocket_watch, spyglass, diving_helmet, ammonite, megalodon_tooth, grand_conch, figurehead, porcelain_teapot, ship_lantern, sextant, music_box, ship_in_bottle, sunken_crown, treasure_chest
- `junk/`: old_boot, tin_can, tangled_net
- `town/`: buildings (fish_shop, harbor_office, post_office, museum_hull, pip_house, cottage_a/b/c, lighthouse, net_shed), boardwalk/pier kit, pilings, crane, props (crate, fish_crate, barrel, rope_coil, lantern_post, hanging_lantern, life_ring, bench, mailbox, anchor, net_rack, buoy_cluster, ice_chest, counter, display_ice, sign_*, flower_pot, tree_pine, grass_tuft, rocks, kelp, iceberg, sea_stack, wreck)

### 5.5 Audio (`Game/Assets/Saltmoss/Audio/{Music,Sfx}`)
All original, synthesized by `Tools/audio`. Music OGG 44.1 kHz stereo (loops seamless); SFX WAV 44.1 kHz.
Voice blips are synthesized at runtime by `VoiceBlips.cs`.

### 5.6 Code layout
`Game/Assets/Saltmoss/Scripts/Runtime/{Core,Clay,Characters,Boat,Sea,Fishing,Shop,Dialogue,UI,Audio,World,Trailer}`,
editor builders in `Scripts/Editor`, shaders in `Shaders/`. Namespace `Saltmoss`. The world scene is generated by
`Saltmoss.EditorTools.Pipeline.Content` (headless) — scenes, materials and prefabs are build products, not sources.
