# The plush family SDK (`characters.film`)

How to make a video with the plush animals. One module, `characters.film`, covers the stage, the cast, the camera,
the acting, the checks and the render. This page is all a video script needs; `README.md` describes the modules
underneath.

## Setup

Run scripts with srlocations' interpreter, from any folder:

```
/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python my_video.py
```

```python
import sys
sys.path.insert(0, "/home/dev/data/sr-data")      # the folder that holds characters/
from characters import film
```

A render uses the GPU. On this host run it under the guard, which pauses it if the card gets hot:

```
python3 /home/dev/data/ai3d/scripts/gpu_guard.py --pause 78 --resume 68 --abort 86 --log guard.csv -- <interpreter> my_video.py
```

## A film in twelve lines

```python
f = film.Film("hello", size=(1080, 1080))            # name, picture size in pixels, fps=24
bear = f.add("bear", "idle", at=(0.4, 0, 0))
bunny = f.add("bunny", "idle", at=(-0.4, 0, 0))
f.camera((0, 0.9, 12), look_at=(0, 0.4, 0), lens=110)

bear.look(0.5, bunny).do(1.0, "wave").do(3.0, "jump")
bunny.look(0.8, bear).do(1.6, "giggle").go(4.0, (-0.9, 0.3), style="hops")

f.still("out/hello.png")                 # the picture before anything moves
f.render("out/hello.mp4", seconds=6)     # acted, checked, slimmed, encoded
f.strip("out/hello-strip.png")           # frames of the clip side by side
```

This is `examples/film_hello.py`; it renders in under a minute.

## Sound and subtitles

```python
take = json.load(open("voice/line.json"))                 # ElevenLabs: characters and their times
cat.say(take, at=0.5, audio="voice/line.mp3")             # lip-sync, the voice, and its subtitles
f.music("music/theme.mp3")                                # lowered under the voice by itself
f.sound("sfx/rustle.mp3", at=1.2)
f.render("out/talk.mp4", seconds=6.5)                     # a video with sound and burned subtitles
```

The engine mixes the sounds, lowers music and ambience 12 dB under a voice, and brings the film to -14 LUFS with
a true peak of -1 dB. Subtitles are cut at sentences and commas into two lines of 24 characters, shown at least
0.83 s, with the word being spoken in gold; `f.subtitle_look` (a `soundtrack.CaptionLook`) changes their size,
colours and where they sit (`centre`, a share of the height: 0.69 by default, under the face and clear of a
Reel's own text). A film with no sound and no subtitles renders as a plain silent video, as before. It works in
every finish: with fur, our engine lays the sound and the subtitles over Blender's picture.

## Two finishes

```python
f.render("out/hello.mp4", seconds=6)                                 # paper: our engine's drawn look
f.render("out/hello-fur.mp4", seconds=6, finish="fur")               # soft toys with real fur, in a studio
f.render("out/hello-terry.mp4", seconds=6, finish="terry", quality="draft")
```

| Finish | Drawn by | What it looks like | Cost on this host |
|---|---|---|---|
| `paper` (default) | scene-render | pencil and ink on photographed paper | about 1 s a frame |
| `fur` | Blender Cycles | plush toys with a real pile, studio light, soft shadows, a blurred backdrop | 1.5 s (`draft`), 3 to 5 s (`standard`), about 10 s (`fine`) a frame for one figure filling the frame |
| `terry` | Blender Cycles | the same toys in a napped cloth with no hairs: no fuzzy edge | about 2 s a frame |
| `vinyl` | Blender Cycles | moulded collectible toys: matte vinyl with a soft sheen, glossy shoes, metal badges | about 4 s a frame |
| `lowpoly` | Blender Cycles | faceted low-poly figures: each part cut to a few flat facets, each facet a steady shade | about 1 s a frame at `draft` (two or three figures, 1280x720); other qualities not measured |

The same film, the same acting and camera; only who draws it changes. The Blender finishes need a Python with
bpy 4.2 (`characters.blender.PYTHON`) and use the GPU under the temperature guard. Their frames are kept in
`<out>.frames/` beside the clip, so an interrupted render picks up where it stopped; delete that folder to draw
them again. In them a film has a studio backdrop and lights of its own: set pieces added with `prop()` are drawn,
the paper look's finish is not. What each part is made of (fur, felt, thread, a bead) comes from
`characters/cloth.py`.

## Vinyl people

A second family beside the plush animals: collectible-toy humans (`characters/vinyl3d.py`). The pilot is
`officer`: a peaked cap, a short-sleeved shirt with pockets and a badge, a belt with a pouch and a radio.

```python
f.add("officer", "idle", at=(0.5, 0, 0))
f.still("out/officer.png", finish="vinyl")        # a picture in any finish; `still()` takes `finish=` too
```

There are also low-poly people (`characters/lowpoly3d.py`), made for `finish="lowpoly"`: `sergeant`, a 1 m adult
in the officer's outfit; `cook`, the same body in a toque, a double-breasted jacket and an apron; and
`firefighter`, the same body in a helmet and a turnout coat with reflective bands; `captain`, the officer's
outfit on the second build, a woman; and `anchor`, a news anchor: the man's build in a suit, bare-headed.

A low-poly person is three choices, each written once: a build (`BODIES`: `man`, `woman`: skeleton proportions and
the sections of trunk, hips, limbs, skull and hair), an outfit (`OUTFITS`: `officer`, `cook`, `firefighter`,
`suit`) and a `Person`: colours, and a few options of its own (hair on top of a bare head: `hair_style`, with
`temples` for sides of another colour; `brow`; `shoe` for a low dress shoe, `sole`; `shirt` and `tie`). Shapes
are `Loft`s: octagonal sections stacked along a height, or along a bone
(`Parts.span`), whose corners the finish keeps exactly. Place what lies on one with `Loft.seat` / `Parts.flat`
(a pocket, a badge), `Loft.around` / `Parts.hung` (a pouch), `Loft.band` / `Parts.cuff` (a belt, a stripe), so it
sits on the facets in every view. A section may have another outline than the octagon (`profile=`, `HEX` for
limbs, the skull's face planes), and a loft can ask the finish to break its sides into irregular facets
(`facet=` size and `crease=` depth, in millimetres): cloth and bare arms do, heads and belts do not. Outfit parts
are reusable pieces (`_open_collar`, `_pocket`, `_epaulettes`, `_badge`, `_duty_belt` with `_pouch` and `_radio`,
`_peaked_cap`, `_stand`), placed as shares of the build (`_up`, `_across`), so they fit both builds. Cloth that
lies on a part and follows it is a `_panel` (rows of height and two edges; it bends where the part does). The
suit is made of such pieces, each usable alone: `_jacket` (`_skirt`: the cloth from chest to hem, open in front
over the hips; `_lapels`; `_stand` as its collar; `_flap` pockets; a back seam; `_sleeve_buttons`), a shirt
(`_open_collar` closed over a tie, `_shirt_bib`, `_shirt_cuffs`), `_tie`, `_turn_ups`: a lawyer or a groom is
another `Person` in the same outfit, a presenter in shirt sleeves a new outfit of three of them. Hands (palm,
four fingers, thumb) and boots (sole with a heel, upper) are drawn parts sized by `Body.hand` / `Body.foot`.

Sizes are set from measurements, not by eye: `lowpoly-blender/tools/round.sh` renders the proofs of all five
people and prints, against the officer's reference sheet, the outline match (IoU), how many centimetres each
body band is off (front and profile) and a surface score (contrast, edges and facet size of the cloth).
`tools/poses.py <who> <out>` draws the 16 poses and `tools/count.py <out> <who>...` counts triangles
(about 4,200 for the sergeant, 4,800 for the anchor; the budget is 6,000).

It stands on the same skeleton, so poses, `look`, `go`, `say` and the body actions work on it; it has no paws,
ears, tail or soft body, so the paw actions (`clap`, `shy`, `pat`...) and what trails are not its own
(`film.can("officer")`). It is made for `finish="vinyl"`; the paper look draws it too, and the plush animals can
be rendered in vinyl. Another profession is another `Person` with its own outfit in `vinyl3d.py`.

## Space and time

- Metres. `y` is up; the floor is `y = 0`. A figure is about 0.7 m tall and stands with its feet at `at`.
- A figure with `yaw=0` faces `+z`. Put the camera on `+z` to see faces.
- A camera on `+z` sees `+x` on the **left** of the picture.
- Times are seconds from the start of the clip. Everything an actor is told happens at the time given.

## The cast

`film.CAST`, 22 animals and 9 robots, all with the same poses, actions and moving parts:

`bear` `cat` `pig` `bunny` `redpanda` `quokka` `fennec` `otter` `koala` `pika` `axolotl` `arcticfox` `hippo`
`lion` `tiger` `panda` `eagle` `duck` `dragon` `armadillo` `shark` `treefrog`

The robots: `bip` `zap` `tec` `lata` (Latinha), and three that stand for programming languages: `java` `c`
`python` (Python has a tail), and two that stand for AI assistants: `claude` `chatgpt`. Their antennae move as ears do; they have no tail and no blush.

Dev, Professor Frog, Chick and the Mouse were removed from the cast (2026-11-11). They are kept, as they were,
in `sr-data/characters_legacy/` for the videos made with them.

`film.can(who)` gives `{"poses": ..., "actions": ..., "moves": ...}` for a character.

## Film

| Call | What it does |
|---|---|
| `Film(name, size=(1080, 1920), fps=24, look=None, overlap=0.15)` | A new film. `look` replaces the plush drawing style. `overlap` is how deep (m) one body may run into another before the film is refused. |
| `add(who, pose="idle", at=(0,0,0), yaw=0, lean=0, name=None, **fields)` | Puts a character in, in its first pose; gives its `Actor`. `lean` leans it toward the picture's right, in degrees. A second copy of an animal needs its own `name`. `fields` are the figure's own, e.g. `tail_side=-1`. |
| `camera(eye, look_at, lens=50)` | Where the camera is, what it looks at, the lens in mm. One camera per film. |
| `together(a, b)` | Two actors heads together: placed so the heads touch without merging, and kept apart while they act. |
| `prop(node)` | Adds a srlocations node (a `Box`, a prefab) to the set. |
| `sound(path, at=0, role="effects", gain=0)` | A sound heard from `at`: `"dialogue"`, `"music"`, `"effects"` or `"ambience"`. `gain` in dB. |
| `music(path, at=0, gain=-8)` | Music under the film; it gives way to voices by itself. |
| `subtitle(text, start, end)` | A subtitle of your own (what an actor says is subtitled already). |
| `still(out, size=None)` | A picture of the start. Take it before `render()`. |
| `render(out, seconds, size=None, finish="paper", quality="standard")` | The clip, in our drawn look or as soft toys with fur (see "Two finishes"). |
| `export(folder, seconds)` | The film as plain geometry, one file a frame, for another renderer. |
| `strip(out, columns=6, rows=2, width=480, start=0, seconds=None)` | Frames of the rendered clip side by side. `film.strip(source, out, ...)` does the same for any video file. |
| `perform(seconds)` | The acting without the render (`render()` calls it). For adding keys of your own to `f.loc` before rendering. |
| `check()` | Refuses a film where two heads overlap at the start. |

## Actor

Every method gives the actor back, so calls chain.

| Call | What it does |
|---|---|
| `pose(time, name)` | From `time` it holds this pose. It moves into it with a wind-up and settles. |
| `do(time, action, side="right", scale=1.0, at=None, seed=None, vary=None, seconds=None)` | Plays an action over the pose it holds. `side` is the arm, ear or eye used; `at` turns it to an actor or a point; `seed` and `vary` play it a little differently; `seconds` plays it for that long (a `dance`, a `tap-foot`). |
| `look(time, target)` | Looks at another actor, at a point `(x, y, z)`, or straight ahead again (`None`). The eyes go first, the head follows. |
| `go(time, (x, z), style="waddle", seconds=None, turn=0.7, seed=None, vary=None)` | Travels to a place: `"waddle"` rocks from foot to foot, `"hops"` goes in small hops, and on two legs it can `"walk"`, `"run"`, `"sneak"` (on tiptoe, crouched, looking round) or `"skip"` (`film.can(who)["ways"]`). It turns part of the way toward where it goes and back when it arrives. A `seed` gives its steps their own start and size. |
| more ways for `go(style=)` | `"tiptoe"` (upright on its toes, quick small steps, arms out), `"march"` (knees right up, straight arms swinging), `"stagger"` (slow, off its line, lolling), `"trip"` (a walk in which a foot catches and it saves itself), `"slide-stop"` (a run that ends in a skid, leaning back, half turned), `"leap"` (one long jump: 1.1 s), `"back-away"` and `"moonwalk"` (it does not turn to where it goes: send it to a place behind it), `"cartwheel"` (over on its hands and round, 1.5 s: send it to a place at its side). |
| `climb(time, (x, z), rise=0.12, seconds=None)` | Steps up on to something `rise` metres high: a knee up, the weight over it, and up. It stays that much higher, its shadow with it (put the box there with `f.prop()`); a negative `rise` steps down. |
| `turn(time, to, seconds=0.7)` | Turns on the spot to face another actor, a point `(x, z)` or a direction in degrees (0 faces a camera on +z), the short way round, and stays so. What it looks at stays what it looks at. |
| `sit(time, pose="sit")` / `stand(time, pose="idle")` | Sits down where it stands, into a seated pose, and settles; gets up into a standing one. |
| `lie_down(time, side="right", seconds=1.1)` / `get_up(time, seconds=1.3)` | Lies down on its side where it stands and stays so (its shadow lies flat under it); gets up and stands as it stood. It needs about its own height of room to that side. Give it a face with `pose()`. |
| `wake_up(time, pose=None)` | Plays `wake-up` and leaves it awake in `pose` (default `sit` if it was seated, else `idle`). |
| `hold(time, thing, side="right")` | From `time` it holds a thing in that hand (`film.THINGS`: `"gift"`, `"ball"`, a `"glass"` of wine, a `"mug"` of beer, a `"bottle"`); `None` puts it away. Drinks are drawn half as big again as life, so they read. |
| `drink(time, thing="glass", seed=None)` | Drinks from what it holds: the drink comes to the mouth and tips, the head goes back. With no drink in its hand it has `thing` from the start of the film. |
| `pop_cork(time, seed=None)` | Pops the bottle it holds (it has one from the start if it holds none): a shake, the cork flies off, the foam bursts, and the bottle stays open. |
| `follow(time, leader, gap=0.45, style=None, seed=None)` | Goes where `leader` goes, a moment after and `gap` metres short, in the leader's way of going. Give it after the leader's own `go()` calls. |
| `power_down(time, seconds=1.2)` / `power_up(time, seconds=1.6)` | A robot switches off (its eyes shut, its face leaves the screen, its head sinks) and stays off; it comes back on with a stutter. Robots only. |
| `say(alignment, at, audio=None, subtitles=True)` | Speaks a voice take starting at `at`: the mouth follows the words, the voice is heard in the film, and the words are subtitled. `alignment` is the voice's character timestamps (ElevenLabs); `audio` is the voice file. |
| `acting(energy=, life=, blink=, seed=)` | How it acts: `energy=0` moves without bounce, `life=0` holds still between moves, `blink=False` stops blinking, `seed` fixes its random timing. |

`actor.fig` is the srlocations figure, for what the SDK does not cover.

## Poses

Standing: `idle` `talk` `cheerful` `confident` `smug` `explain` `proud` `ask` `puzzled` `suspicious` `worried`
`sulk` `shrug` `surprised` `yell` `dizzy`

Seated: `sit` `sit-happy` `sit-cuddle` `sit-chat` `sit-wonder` `sit-sleep`

A figure starts standing or seated, as its first pose says, and may change: `sit()` and `stand()` do it (or
`pose()` with a pose of the other kind). While it is seated, actions play their seated versions. Seated, long tails curl beside the body; `tail_side=1` or `-1` in `add()` picks the side.

## Actions

| Action | Seconds | What it does |
|---|---|---|
| `nod` | 0.9 | Two nods. |
| `shake` | 1.0 | Shakes its head. |
| `tilt` | 1.3 | Tips its head to one side. |
| `giggle` | 1.3 | Eyes shut, shoulders shake, blush grows. |
| `surprise` | 0.9 | Eyes pop, brows up, the body stretches. |
| `wink` | 0.8 | One eye shuts, the head tips, a smile. |
| `wave` | 1.6 | One paw sweeps out and back beside the cheek. |
| `palm` | 1.6 | A talking gesture: one open paw comes up in front of the cheek, pad and toe beans to the camera. |
| `cheer` | 1.5 | Both paws up. |
| `clap` | 1.7 | Paws together, three times a second. |
| `shy` | 2.0 | Paws on the cheeks, eyes shut. |
| `pat` | 1.6 | Pats its tummy. |
| `bounce` | 1.0 | Two dips of the knees; seated, the back and shoulders. |
| `hop` | 0.75 | A small hop off the ground. |
| `hops` | 1.5 | Three quick hops. |
| `jump` | 1.1 | A crouch, a jump of 20 cm, a landing that squashes. |
| `kick` | 1.8 | Marches on the spot; seated, kicks its legs in turn. |
| `twitch` | 0.35 | One ear flicks. |
| `perk` | 1.2 | Both ears prick up. |
| `droop` | 2.2 | Ears and eyelids droop, the head sinks. |
| `wag` | 1.6 | The tail wags. |
| `point-at` | 1.8 | One arm goes out toward something: `do(t, "point-at", at=actor or point)`; without `at`, ahead and out. |
| `tada` | 1.8 | Here it is: both arms flung open, the chest up. |
| `beat` | 1.8 | The hands beat in front of the body, in turn: play it under a line of speech. |
| `think` | 2.6 | A hand to the chin, the head tipped, the eyes up and away. |
| `idea` | 1.5 | A start, a small hop, one arm up beside the head, the eyes wide. |
| `shrug` | 1.6 | The shoulders up, both hands out, the head to one side. |
| `no-no` | 1.8 | A raised hand wags at the wrist while the head shakes, eyes shut. |
| `come-here` | 2.0 | The hand goes out and curls back to the face, twice a second. |
| `listen` | 2.2 | Leans to its side, a hand by the ear, that ear turned out. |
| `whisper` | 2.4 | Leans over to its side, a hand beside the mouth, the eyes half shut. |
| `count` | 2.4 | One, two, three: a hand held up beats once for each, the head nodding along. |
| `facepalm` | 2.4 | A hand up to the face, the head dropped into it, the eyes shut. |
| `chin-rub` | 2.6 | Weighs something up: a hand strokes the chin, the eyes down and narrowed. |
| `thumbs-up` | 1.8 | Well done: a fist pushed out in front, a nod with it, a wink. |
| `salute` | 1.8 | Draws itself up and the hand snaps to the temple. |
| `shush` | 2.2 | A hand to the lips; it leans in and looks from side to side. |
| `air-quotes` | 2.0 | Both hands up beside the head twitch twice, the head to one side. |
| `present` | 2.2 | An open hand sweeps out to its side; it looks at the thing, then back. |
| `stop` | 1.8 | A flat palm thrown out in front, the body braced behind it. |
| `so-so` | 2.2 | A hand held out rocks from side to side, the head rocking with it. |
| `gasp` | 1.6 | The breath goes in at once, both hands fly to the mouth, the eyes wide. |
| `cheer-jump` | 1.3 | Hurray: a jump with both arms thrown up. |
| `facepalm-double` | 2.8 | It cannot look: the head down into both hands, shaking slowly. |
| `eye-roll` | 1.9 | The eyes go round over the top from one side to the other, the head after them. |
| `gulp` | 1.6 | A nervous swallow: it stiffens, the shoulders up, and the head dips as it goes down. |
| `relief` | 2.6 | A hand across the brow, then the air goes out and the shoulders drop. |
| `tantrum` | 2.4 | The fists pump, the feet stamp in turn, the head shakes, the mouth wide. |
| `faint` | 3.6 | It sways, goes over on to its side (`side=` says which), lies there, and gets up again. Leave room: two that faint toward each other fail the heads check. |
| `blush-hide` | 2.4 | Too shy to look: it turns away, both hands on its cheeks, blushing, squirming. |
| `startle-jump` | 1.0 | A fright: straight up off the ground, stiff, arms flung wide. |
| `scratch-head` | 2.2 | Puzzled: a hand scratches the side of the head, the head tipped toward it. |
| `hiccup` | 2.8 | Small jolts that come unevenly, the shoulders jumping, a little off the ground. |
| `cough` | 2.0 | A fist to the mouth, the body jerking forward three times. |
| `rub-eyes` | 2.4 | Sleepy: both fists rub the eyes. |
| `wake-up` | 3.0 | It stirs, then a long stretch with a yawn. `actor.wake_up(t)` plays it and leaves the actor awake (`sit` or `idle`). |
| `check-wrist` | 2.4 | The forearm comes up across the chest, the head goes down to it, a foot taps. |
| `dust-off` | 2.2 | It brushes itself down: both hands sweep the tummy in turn, the head down to look. |
| `tummy-rub` | 2.4 | Hungry, or full: a hand goes round and round on the tummy. |
| `laugh` | 2.0 | A real laugh: the head back, the mouth wide, the body shaking, hands on the tummy. |
| `cry` | 2.6 | The head down into the hands, the shoulders jerking, a tear. |
| `sigh` | 2.2 | The chest and shoulders rise as the air goes in, then everything sinks. |
| `yawn` | 2.6 | The head back, the mouth as wide as it goes, both arms stretched out. |
| `shiver` | 1.8 | Hunched, the arms held in, everything trembling. |
| `flinch` | 1.1 | Jerks back and turns its face away from its side, a hand up between. |
| `cower` | 2.4 | Crouched low and small behind its hands, wide-eyed, trembling. |
| `huff` | 1.9 | A puff of the chest, then the face turned away to its side, chin up. |
| `stomp` | 1.5 | The foot of its side comes down twice, the body giving on each landing. |
| `puff` | 2.2 | Proud: the chest out, the shoulders back, the chin up, eyes shut. |
| `sneeze` | 1.7 | The head goes back as the breath is drawn in, quivering, then snaps forward. |
| `oh-no` | 2.0 | Both hands to the cheeks, the eyes wide, the head going from side to side. |
| `look-around` | 2.6 | Looking for something: the head sweeps one way and the other. |
| `double-take` | 1.6 | An idle glance to its side, away, then the head whipped back there, eyes wide. |
| `peek` | 2.0 | The whole body leans out to its side, the head level, to see round something. |
| `nod-off` | 3.0 | The head sinks, the eyelids come down, then it starts awake. |
| `love` | 2.4 | Both hands under the chin, the head to one side, swaying, eyes shut, cheeks glowing. |
| `bow` | 2.0 | A bow from the hips, a hand on the tummy, eyes shut. |
| `stretch` | 2.6 | Both arms up as far as they go, the back arched, leaning one way and the other. |
| `crouch` | 1.8 | Down on bent knees and up again; seated, it ducks. |
| `spin` | 1.3 | A pirouette: a wind-up, then all the way round toward its side, arms out. |
| `dance` | 4.0 | Side to side on bending knees, one arm up as the other comes down; `seconds=` for longer. |
| `tap-foot` | 2.4 | Waiting, not pleased: the foot of its side taps, arms folded; `seconds=` for longer. |
| `wobble` | 2.6 | Dizzy: the body goes round in a slow circle, the head a beat behind, eyes in spirals. |
| `fall` | 2.6 | A tumble: it trips, tips back on to its bottom, sits there dazed, and gets up. |
| `high-five` `hug` `pat-other` `give` `take` | 1.5 to 2.6 | One arm goes to a point. Use the film's own calls below, which give two actors the same point and the same time. |
| `glitch` | 1.4 | The head and shoulders jerk; a robot's screen cuts in and out. |
| `screen-icon` | 2.0 | Robots only: the screen shows a picture in place of the face: `do(t, "screen-icon", icon="heart")`, or `question`, `exclaim`, `dots`; `seconds=` for longer. |

**Two at once** (calls of the film, not of an actor): `f.high_five(time, a, b)` slaps their hands at a point
between them; `f.hug(time, a, b)` puts an arm of each round the other (stand them close first);
`f.pat(time, a, b)` has `a` pat `b` on the head, and `b` like it; `f.toast(time, a, b, c, thing="glass")`
has two or more touch glasses at a point between them (whoever holds no drink has `thing` from the start); `f.give(time, a, b, "gift")` hands a thing
over: `a` holds it from the start of the film, and it changes hands as they meet. Each takes `seed=`: the two
play their own variation but keep the same time. An arm that cannot reach goes as far as it can and is drawn
the rest (up to `Spec.stretch` times its length: 1.5 for the plush family); the points are taken from where the actors stand at the start of the film.

**One arm, one length.** A plush arm is 0.166 m from shoulder to wrist and keeps that length: it bends at the
elbow for a hand nearer than it reaches, and is drawn longer only for a hand further off (`Spec.stretch`) or to
go round the head (`Spec.detour`, 2: never more than twice its length). The head is bigger than the arm is long,
so a hand does not reach the forehead or the top of the head: it stops as near as it gets with the forearm clear
of the head (`MascotFigure.arm_points`). Write actions for a hand at the cheek, the chin or the side of the head.

`do(time, action, at=actor or point)` turns any one-sided action to that actor or point: it plays on the arm of
that side (instead of `side=`), and `point-at` points there. **Never twice the same.** An action is written once, so it plays the same every time and on every character.
`do(time, action, seed=3)` plays it a little differently: its size (up to 15% either way), its length (up to
9%), and where its beat starts (a wave's sweep, a laugh's shake). The same seed always gives the same playing,
so a clip renders the same again; another seed gives another. `vary=0.3` asks for more, `vary=0` for none.
`actor.acting(vary=0.15)` varies every action of that actor from the actor's own seed, each time it plays one,
without a seed each: give it to a group and no two wave alike. When an action starts never changes. Without
`seed` or `vary`, actions play exactly as written, as they always have.

`examples/film_cheers.py [seed]` pops a bottle, has three toast and drink. `examples/film_together.py [seed]` plays the calls for two, a gift given, a tumble, one following another, and
a robot's screen. `examples/film_ways.py [seed]` plays the ten ways added on 2026-11-12, with a box to climb; `examples/film_moving.py [seed]` turns two characters to each other, walks, runs, sneaks and skips them, and
sits them down and up again. `examples/film_actions.py talking|reactions|everyday|moving|signs|strong|daily|arms [seed]` plays a
set of ten on a bear and a robot, each action with a seed of its own, and writes a sheet of them
(`examples/out/film-<set>-sheet.png`); another seed gives another take.

A seated figure does not leave its seat: `hop`, `hops` and `jump` become a bounce.

## What happens without being asked

A soft contact shadow lies under every figure, on what it stands or sits on; it stays down and shrinks while the
figure is off the ground. `add(..., shadow=0)` leaves it out.

Breathing and a slow sway; blinks, some of them double; small glances of the eyes aside and back; ears and tails
that trail the head and the body; the weight settling on one leg and then the other (standing) or the feet
swaying in turn (seated). Each actor's timing is its own, from its name.

**One list of parts for the whole film** (`fixed.py`). When the paper finish is rendered, each actor gets a place for
every part it ever shows (a lid, an open mouth, a thing in its hand), and each part's size is keyed on every
frame. The scene then holds the figure once, and a body that squashes, an arm that stretches and a mouth that
opens change on every frame. Before this the paper finish wrote the whole figure again at each blink and kept
every part's size frozen in between: frames of a clip measured 18 to 34 dB against stills of the same moments
while a figure acted, and are now at 40 to 42 dB (the video codec's own floor) on every frame measured, for a
plush animal, a robot, the officer and the sergeant. `film.parts` says how many places each actor has. To
compile the location yourself, call `film.settle()` first; a scene that calls `motion.perform()` itself calls
`fixed.settle(loc, figs, seconds, fps)` after its last key.

**A robot's eyes are a picture on its screen**: in a blink, a wink or a narrowed look the lit eye flattens, and no
lid is laid over it.

## What the SDK checks

It raises `film.FilmError`, with what there is instead, for:

- a character that is not in the cast, a pose or an action it does not have;
- a film with no cast or no camera, a `render()` with no length, a still asked for after the render;
- two heads that overlap at the start, or at any moment of the acting (it gives the names, the depth and the time);
- a body that runs more than `overlap` (15 cm) into another at any moment: a figure walking through another;
- a trip that starts before the last one has ended;
- a scene file that is still over the engine's 256 MB after slimming;
- a finish or a quality that does not exist, and a Blender that cannot be run or did not draw every frame.

## Limits

- **Travel does not go round other characters.** A path through another figure is refused, not corrected: send
  it somewhere clear. Smaller contacts (neighbours' ears or paws crossing while they act) are allowed, printed
  when the film is performed and kept in `film.contacts`: look at them in the strip.
- **A scene file may hold 256 MB**, with our build of the engine (`/home/dev/data/scene-render-patched`: 0.8.0
  with the document limit raised from 64 MiB to 256 and from 4 to 16 million XML nodes; its frames are identical
  to the official binary's). Eight figures talking and acting for 8 seconds at 24 fps make 63 MB (most of the
  file is one key per frame for each part), so about four times that fits. A large document loads slowly and
  takes memory: 69 MB in 20 s with 4 GB, 238 MB in 160 s with 12 GB, before the first frame is drawn. Past the
  limit, or to keep loading short, render in pieces and join them, or use `fps=12`.
- **Paws do not reach the muzzle or the eyes**, hold nothing and have no fingers.
- **Tails are hidden from the front when standing**; they show seated, in profile and in three-quarter views.
- **Lip-sync** (`motion.lipsync`) was measured on real ElevenLabs takes (microentrevistas ep01-ep04, pt-BR) by
  the session that built it: the mouth follows the voice at lag 0; there are no f/v or small-u mouth shapes yet.
  `actor.say()` is the same code; it was run once with a real take (lip-sync, voice and subtitles), and the
  tests run it with made-up timings.
- **The fur finish is new.** It was looked at in frame strips, not watched: the pile may shimmer from frame to
  frame. An eyelid in a blink is a patch of cloth with little pile. There are no seams or embroidery yet, and the
  set is a plain studio. A scene with many figures costs more than the times above (one or two were measured).
- **Nothing judges how the motion looks.** The tests below only prove that nothing breaks.

## Tests

```
cd /home/dev/data/sr-data
PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
$PY -m pytest characters/tests -q -m "not slow"     # about 20 seconds: run this after any change
$PY -m pytest characters/tests -q                   # everything, about 5 minutes: before a render that matters
```

Nothing is rendered. The slow ones play every action and every pose on the whole cast; the quick ones cover the
film's checks and errors, the rig, the export, the finishes, sound and subtitles, the slimming and the vinyl people.

## Underneath

| Module | What it holds |
|---|---|
| `film.py` | This SDK. |
| `motion.py` | `perform()`: the acting between poses, the gaze, the face, the trips. Re-exports `actions` and `speech`. |
| `actions.py` | The action library: `Action`, `ACTIONS`, `PAW_ACTIONS`, `GAITS`. A new action goes here. |
| `speech.py` | Lip-sync: `lipsync()` and its `LIP_*` constants (also reached as `motion.lipsync`). |
| `staging.py` | Heads together, overlap checks. |
| `clip.py` | Scene files slimmed for the engine. |
| `fixed.py` | One list of parts for a figure's whole film, each part's size keyed (`settle()`, `exact()`). |
| `soundtrack.py` | Sounds and subtitles written into the scene (sr-core's audio mix and caption track). |
| `export.py` | The film as plain geometry, frame by frame. |
| `cloth.py` | What each material is made of (fur, felt, thread...), and the pile's length. |
| `blender/` | The fur and terry finishes: `render_frames.py` runs in Blender. |
| `plush3d.py`, `vinyl3d.py`, `lowpoly3d.py`, `robots3d.py` | The families: plush animals, vinyl people, low-poly people, the robot kit. |
| `figures.py` (`mascots3d.py`) | The figure every family stands on. |
| `kit.py` | Vectors, tubes, blocks, the paper look and finish, the stage. |
| `expression.py` | `Pose` and the mouth vocabulary. |
| `poses.py` | The poses. |
