# characters: the plush family, for any video

Our cast is the plush family: 22 soft-toy animals and 9 robots (below), each **one 3D model with a skeleton**. The
render turns the model into the drawn 2D picture and the camera decides the angle
([decisions/0001](../decisions/0001-every-character-is-a-3d-model.md)). Every video under `sr-data/` takes its
characters from here, so a change made here reaches every video the next time it is built.

**To make a video, read [`SDK.md`](SDK.md)**: `characters.film` is the front door. This page describes what is
underneath.

Dev, Professor Frog, Chick and the Mouse were removed on 2026-11-11 (the operator: "vamos focar na familia de
pelucia"). They are kept as they were, with their drawings, sheets and cut-outs, in
[`../characters_legacy/`](../characters_legacy/), which the videos made with them import (`reel-recreation`,
`classroom`, `hybrid`, `plush-reels/crowd.py`). Nothing new is built there.

## The robots (`plush3d.ROBOTS`)

Bip `bip`, Zap `zap`, Tec `tec` and Latinha `lata` (the operator, 2026-11-11) are in the family: the same
skeleton and size, so they take every pose, action and film call the animals do. They are machines, not toys
(the operator: "eles nao precisam parecer brinquedos"; a first version with round heads and a pale oval face
read as Teletubbies): a square head and body (`Animal.boxy`, a superellipsoid: `mascots3d.box_egg`), a dark
screen for a face (`Animal.visor`) on which the eyes, brows and mouth are lit in the robot's own colour
(`Animal.led`) inside a metal bezel, metal limbs with a dark cuff at each wrist, rivets and a neck ring; no
blush, no paw pads, no tummy patch. The lit eyes carry no shine (a dark notch read as a squint). Each has its own
head gear and chest: Bip an antenna, side bolts and a core light; Zap two antennae and buttons; Tec headphones
and a dial; Latinha a lamp and battery bars. `staging` still treats a head as an ellipsoid, and a square head
is bigger at its corners: look at robots that lean together.

![robots](sheets/3d/plush-lineup-bip-zap-tec-lata.png)

Three more stand for programming languages (the operator, 2026-11-11), by association and never with a
language's logo: **Java** `java` is a white coffee mug (a red handle on its head, red hands and feet, steam rising, a coffee bean on its
chest); **C** `c` is a plain, strict blue box with white hands, a pointer's asterisk on its antenna and its
letter on its chest; **Python** `python` is yellow with blue, a snake coiled in a stack on its head, a snake's tail and
indented lines of code on its chest. No two are alike (the operator asked for better colours after a first pass where C and Python were both
blue-grey, and for Java to stay white, not red).

![language robots](sheets/3d/plush-lineup-java-c-python.png)

Two stand for AI assistants (the operator, 2026-11-11), also without a logo, each in its product's colour with
a speech bubble on its chest: **Claude** `claude` is warm clay with cream hands, a rising sun (a half disc and seven rays) on its head
and lines of text in its bubble; **ChatGPT** `chatgpt` is green with white hands, a ring antenna and three dots
in its bubble.

![assistant robots](sheets/3d/plush-lineup-claude-chatgpt.png)

## Start here: a film in a few lines (`film.py`)

**The SDK guide is `SDK.md`**, in this folder: setup, the cast, every call, poses, actions, checks, limits.

```python
from characters import film

f = film.Film("hello", size=(1080, 1080))            # fps=24 by default
bear = f.add("bear", "idle", at=(0.4, 0, 0))         # any name of film.CAST (the plush family), in a pose of its own
bunny = f.add("bunny", "idle", at=(-0.4, 0, 0))
f.camera((0, 0.9, 12), look_at=(0, 0.4, 0), lens=110)

bear.look(0.5, bunny).do(1.0, "wave").do(3.0, "jump")
bunny.look(0.8, bear).do(1.6, "giggle").go(4.0, (-0.9, 0.3), style="hops")

f.still("out/hello.png")                 # the picture before anything moves
f.render("out/hello.mp4", seconds=6)     # acted, heads checked, scene file slimmed, encoded
f.strip("out/hello-strip.png")           # frames of the clip side by side
```

- An actor's `pose(time, name)`, `do(time, action, side=)`, `look(time, actor | point | None)`,
  `go(time, (x, z), style=)` and `say(alignment, at=, audio=)` chain; `acting(energy=, life=, blink=, seed=)`
  passes options to `motion.perform()`.
- The cast of a film is the plush family (the operator, 2026-11-11).
- `film.can(who)` gives a character's poses, the actions it can play and what moves on it; asking for something
  a character cannot do raises `FilmError` with what there is instead.
- `f.together(a, b)` puts two heads together without merging and keeps them apart while they act; `f.prop(node)`
  adds a set piece; `add(..., lean=7)` leans a figure toward the picture's right.
- The modules below stay usable for what the film does not cover: `f.loc` is the Location, `actor.fig` the figure.
- `examples/film_hello.py` is this film.
- Tests: `SRLOCATIONS_PY -m pytest characters/tests -q` (about a minute, nothing rendered) builds every animal in
  every pose, plays every action standing and seated, travels, talks, and checks the film's errors and the scene
  slimming. Run it after changing `motion.py`, `actions.py`, `speech.py`, `mascots3d.py`, `plush3d.py`, `film.py` or `clip.py`.

## Seated poses and groups (`staging.py`)

Every plush animal also sits: `sit`, `sit-happy`, `sit-cuddle` (both paws under the chin), `sit-chat`, `sit-wonder`
and `sit-sleep` (`poses.PLUSH_SEATED`; `Pose.extras` "sit" puts the legs out in front, and `arms="cuddle"` is the
paws-together gesture). A seated figure rests on whatever its `at` is: the floor or the top of a step. The Tree
Frog (`treefrog`) is the family's frog; `frog` stays Professor Frog, the older mascot.

Two heads leaning together merge into one blob as soon as they overlap. `staging.nuzzle(a, b)` slides `b` along x
until its head just touches `a`'s, and `staging.merged(figs)` lists any pair whose heads still overlap, so a scene
can refuse to render. `../plush-steps/scene.py` is the example: eight animals on three steps, two pairs with their
heads together.

## Acting (`motion.py`)

`location.move(fig, t, pose=...)` alone blends every joint on one curve from key to key: the figure drifts the whole
time, every part lands on the same frame and the face never changes. **Animate the cast with `motion.perform()`
instead**:

```python
from characters import dev3d, motion
fig = loc.add(dev3d.figure("idle", name="dev"))
motion.perform(loc, fig, [(1.0, "ask"), (2.5, "explain"), (4.0, "shrug"), (5.3, "surprised"), (6.6, "idle")])
```

On top of the poses, any character plays **actions** and directs its **gaze**:

```python
motion.perform(loc, bear, actions=[(2.0, "giggle"), (5.6, "wave", {"side": "left"})],
               gaze=[(0.9, bunny), (4.6, None)], fps=12)      # look at the bunny, then ahead again
```

- `motion.ACTIONS`: giggle, nod, shake, tilt, wave, cheer, bounce, surprise. An action moves the body over whatever
  pose is held and takes the face with it (a giggle shuts the eyes into arcs), then gives both back. A seated
  figure bounces with its back instead of its knees.
- `gaze=[(time, figure | (x, y, z) | None)]`: the eyes go first, through a blink, and the head follows with its share.
- **Soft bodies**: perform() squashes the body and head in the wind-up,
  stretches them as the move goes and lets them wobble as they settle; a bounce or a surprise squashes and stretches
  too, and a wave or a cheer draws the arm up to 45% longer so it reads on stubby arms. These are fields of the
  figure (`squash`, `arm_left`, `arm_right`), so a still can use them: `m.figure("bear", "idle", squash=-0.15)`.
- **Ears** (the plush family): `ear_left`, `ear_right` (degrees out from the head, negative = drawn in) and
  `ear_back` are fields of the figure. perform() makes them trail the head's tilt and nod, draw in on a stretch and
  spread on a squash, flick now and then, and react to actions; `twitch`, `perk` and `droop` are ear-only actions.
- **Tails** (the plush family): `tail_sway` and `tail_lift` are fields of the figure. perform() makes the tail trail
  the body's lean, sway slowly, lift on a stretch and wag with giggle, cheer, wave and bounce; `wag` is the
  tail-only action. Tails and long ears bend along their length.
  Seated (a `sit-*` pose), long, bushy and tapering tails rest curled round beside the body with the tip in
  front, so they show from the front; `tail_side` (1 or -1) picks the side, and the tip flicks out and lifts.
- **Arms that read as arms** (2026-11-11, after the operator saw them as "uma massa amorfa"): an arm is its own
  ink group with its paw (`arm_l/...`, `arm_r/...`), so a line runs round it where it lies over a body of the same
  colour; it is slim (`arm_r` 0.037) with a paw half again as wide. In the body's ink group, as it was, a resting
  arm had no edge against the body. Feet lift (`foot_left_up`, `foot_right_ahead`, ...): the legs are hidden in
  the body, so `kick`, a march, a waddle and a hop show in the feet.
- **Arms and paws** (the plush family): a paw is a mitten with a wrist (`wrist_left`, `wrist_right`) and, on a
  raised paw, a pad and three toe beans. The arm actions put the paw where it reads and draw the arm as long as
  that takes (`mascots3d.gesture_stretch`, at most 1.8): `wave` sweeps the paw out and back beside the cheek with
  the paw flapping a beat behind, `cheer` raises both, `clap`, `shy` (paws on the cheeks) and `pat` (the tummy)
  are plush-only. The muzzle and the eyes are out of reach of these arms: no paw-to-mouth or eye-rub.
- **A face that moves between its drawings** (the plush family): perform() keys `lid` (the eyelids come down
  before a blink and rise after it; `droop` gives heavy eyes), `mouth_open` (an open mouth opens and closes over
  a few frames), `eye_scale` (wide eyes squint, pop, settle), `blush` (grows with `shy` and `giggle`) and
  `look_x`/`look_y` (the eyes dart ahead of the head, and shift a little the way they look).
  Line mouths (flat, smile, frown, smug, wavy) and brows turn into each other over 0.12 s (`mouth_from`,
  `mouth_mix`, `brows_from`, `brow_mix`; brows that appear grow from their middle). `wink` shuts one eye
  (`lid_left`, `lid_right`). The eyes make small darts aside and back on their own, and now and then a blink is
  double.
- **Off the spot**: `hop`, `jump` and `hops` leave the ground (a crouch, air time, a landing
  that squashes and wobbles; ears and tails trail the rise and the fall; a seated figure bounces instead), `kick`
  marches on the spot or, seated, kicks the legs in turn. `perform(..., travel=[(time, (x, z), {"style":
  "waddle" | "hops"})])` takes the figure to a place in the location, turned part of the way toward where it
  goes, and back to its facing when it arrives. These key `hop`, `step_x`, `step_z` (not `at`), and with travel
  `yaw` and `roll`. Idle: seated feet sway in turn; a standing figure settles its weight on one leg, then the other.
- `motion.stagger(figs, "nod", start=2.0)` gives a group the same action a few frames apart.
- Acting moves heads, so after perform() run `staging.clear_in_motion(loc, a, b, fps)` on figures that lean
  together and `staging.merged_in_motion(loc, figs, fps)` as the check.
- Eight figures acting for 8 s at 24 fps make a scene file of about 63 MB; the engine takes 256 MB (see Scene
  files below), and loads a large document slowly.

A beat is when a pose is hit; it is held until the next. perform() adds a wind-up and a dip in the knees before a
change, springs that overshoot and settle, overlap (body, then chest, arms, head, hands; a fast arm bends at the
elbow), a living hold (breathing, sway, head drift), and the face: the expression changes as the move starts, through
a blink, and the figure blinks while it holds. `energy` scales the wind-up, dip and overshoot, `life` the hold's
motion, `seed` the breathing phase and blink times (from the figure's name by default, so a group is never in
unison). `examples/motion_demo.py bear|cat|...` renders before and after side by side
(`examples/out/motion-demo-<who>.mp4`, about a minute at 1280x720).

In a scene: `dev3d.figure("ask", name="dev", at=(x, 0, z), yaw=...)` is a srlocations `Figure` to `location.add()`;
`location.move(fig, t, pose=dev3d.controls(POSES["dev"][name]))` animates it; `dev3d.look()` is the look (pencil and
pen) and `dev3d.finish(scene, w, h)` the photographed paper. Yaw 0 faces a camera on +z. How it is built, and what the
first model taught for the others: [decisions/0001](../decisions/0001-every-character-is-a-3d-model.md).

`sheets/` shows each legacy drawing's full set (`python3 sheet.py --legacy` redraws them); `cutouts/` holds every
pose as a transparent PNG (`python3 cutouts.py`).

## Scene files (`clip.py`)

The engine refuses a scene document over 256 MiB (our build of 0.8.0 in `/home/dev/data/scene-render-patched`;
the official binary stops at 64 MiB), and a cast acted by `perform()` is keyed on every frame. Always
write a 3D scene with `clip.package(scene, path)` in place of `portable.package(scene, path)`, or make the video
in one call with `clip.encode(renderer, scene, out)`. `encode` asks the engine for `clip.PARALLEL` (3) time segments at once
(`encode --parallel`), which halves the time on one GPU (51 s to 26 s for 509 frames at 1080x1920; 6 give no
more); the picture matches the serial one to 50 dB and the sound to the sample. A scene that runs the engine
itself passes `"--parallel", str(clip.PARALLEL)`. `clip.encode(..., workers=True)` and
`Film.render(out, workers=True)` also hand chunks of the video to the engine on three other machines (`scene-render
serve` on pve-note-1, pve-dev-note-01 and pve-desk-1, two chunks at once each; the hosts and the token are in
`clip.FARM`): 30 s to 14 s on the same 509 frames. A scene that runs the engine itself passes `env=clip.engine_env(True)`. With the worker
off the render is local, with a note. The two GPUs differ along outlines (36.8 dB), so frames that are measured or
compared are rendered with `workers=False`; without the argument the environment decides (`SR_WORKERS`,
`SR_WORKER_TOKEN`). `/home/dev/data/scene-render-patched/README.md` says how to start the worker. It drops the indentation (each element keeps its line: the
engine loads one long line very slowly), writes key times with five decimals, and drops the keys that a straight
line between their neighbours already gives, within 4 units of the last digit written (then 20, then 60, only
if the document would not fit). On one figure the document came out at 58% of its size, with frames at 69 dB
PSNR or better against the unslimmed one. A document still over the limit is refused with what to do.

## Files

| File | What |
|---|---|
| `SDK.md` | how to make a video: setup, every call, poses, actions, checks, limits |
| `film.py` | the SDK: `Film`, `Actor`, `can()`, `strip()` |
| `motion.py` | `perform()`: acting between poses, gaze, face, travel; re-exports `actions` and `speech` |
| `actions.py` | the action library: `Action`, `ACTIONS`, `PAW_ACTIONS`, `GAITS`; a new action goes here |
| `speech.py` | lip-sync: `lipsync()` and the `LIP_*` constants (set them here, not on `motion`) |
| `staging.py` | `nuzzle()`, `merged()`, `clear_in_motion()`: heads together without merging; `bodies()`, `bodies_in_motion()`: whole bodies that run into each other (srlocations.collision) |
| `soundtrack.py` | `apply()`, `cut()`, `cues_of()`: sounds mixed and subtitles burned in by the engine (sr-core audio mix and caption track) |
| `export.py` | `frames()`: a performed location as plain geometry, one file a frame, for another renderer |
| `cloth.py` | `kind(material, part)`: what each material is made of (fur, felt, stitch, eye...), `pile()` its length |
| `blender/` | the fur and terry finishes: `render()` runs `render_frames.py` in Blender Cycles under the GPU guard |
| `fixed.py` | `settle()`: one list of parts for a figure's whole film, sizes keyed on every frame; `exact()` gives the parts as drawn |
| `clip.py` | `package()`, `encode()`: scene files slimmed for the engine, which refuses documents over 256 MiB |
| `vinyl3d.py` | vinyl people: collectible-toy humans that draw all of themselves on the family's skeleton; the officer is the pilot |
| `lowpoly3d.py` | low-poly people for the `lowpoly` finish: builds (`man`, `woman`), outfits (`officer`, `cook`, `firefighter`, `suit`) and five people (`sergeant`, `cook`, `firefighter`, `captain`, `anchor`), drawn as `Loft` sections |
| `plush3d.py` | the plush family: each animal's colours, ears, muzzle, tail, face; the plush look; sheets |
| `mascots3d.py` (`figures.py`) | `MascotFigure`: the figure every family is built on (body, arms, paws, legs, mouth, gestures by IK). `figures` is the name to import in new code; the code moves there once no other session is editing `mascots3d.py` |
| `kit.py` | the kit every family is drawn with: `unit`, `cross`, `scaled`, `basis`, `tube()`, `shape()`, the pencil-and-ink look, the paper finish, `stage()`, `render()` |
| `dev3d.py` | the old name of `kit.py`: imports everything from it, old private names too |
| `poses.py` | `CANON` (the 16 poses every character has), the seated poses, `POSES` |
| `expression.py` | `Pose` and `MOUTHS`: how a face and arms are set |
| `doodle.py` | the 2D drawing kit under the marker style (it still exports `Pose` and `MOUTHS`) |
| `marker.py`, `paper.py`, `shaders/` | the paper, the pencil shader and the photographed-paper finish |
| `__init__.py` | `CAST`, `POSES`, `check()`, the paths of the engine and the interpreter |
| `sheets/` | model sheets rendered from the models |
| `examples/` | `film_hello.py` (the SDK's example), `motion_demo.py` (pose-to-pose against acted) |
| `tests/` | by area: `test_plush.py` (cast, acting, film), `test_rig.py`, `test_vinyl.py`, `test_lowpoly.py`, `test_finishes.py`, `test_soundtrack.py`, `test_clip.py`; `helpers.py`, `conftest.py`. All: about 5 minutes; `-m "not slow"`: about 20 seconds |

## Gotchas

- naga (GLSL -> WGSL): never assign to a function parameter in a shader; the hash returned 0 everywhere.
- The engine splits large effect passes into tiles: `uv` jumps between tiles, `sr_PixelCoord` does not. Use
  `sr_PixelCoord` for patterns.

