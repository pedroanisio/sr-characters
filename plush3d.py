"""The plush family: Bear Cub, Kitten, Piggy and Bunny as 3D models (sr-data/decisions/0001).

Soft toys with a baby's proportions (cuteness reference: 1990s plush-animal TV ads): a big round head of its own, a
short pear body, thick stubby limbs with round paws, a muzzle, blush, pastel fur. They are one family so they
compose: the same skeleton (`BUILD`), the same height, the same body and head; only colour, ears, muzzle and tail
differ. Built on mascots3d's figure (the mannequin skeleton, IK gestures, the shared face), drawn by dev3d's look
and paper finish: the only 2D is that paintover on the 3D render.

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    $PY characters/plush3d.py sheet bear        # sheets/bear.png (and cat, pig, bunny; none = all four)
    $PY characters/plush3d.py lineup            # sheets/3d/plush-lineup.png: the family, front, 3/4, profile
"""

from __future__ import annotations

import math
import subprocess
import sys
from dataclasses import dataclass
from dataclasses import replace as _replace
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "characters"

from srlocations.geometry import Vec3  # noqa: E402
from srlocations.stock.mannequin import Build  # noqa: E402

from . import mascots3d as m  # noqa: E402
from . import paper  # noqa: E402
from .dev3d import SHADER, InkByMaterial, PencilFlat, ROOT, render, tube  # noqa: E402
from srlocations.looks import Cel, Look, Pass, Stage, channels  # noqa: E402

SOFT_SHADE = Path(__file__).resolve().parent / "shaders" / "soft-shade.glsl"

COLOURS = {
    "bear.fur": "#C9A07A", "bear.light": "#F1DFC6", "bear.nose": "#5A3A2A",
    "cat.fur": "#F3B87A", "cat.light": "#FBEBD6", "cat.stripe": "#D98E4E", "cat.nose": "#EE9C98",
    "pig.fur": "#F6C3C3", "pig.light": "#FBE3E1", "pig.snout": "#EFA3A8", "pig.nostril": "#A85F69",
    "bunny.fur": "#F5F1E9", "bunny.light": "#FFFFFF", "bunny.inner": "#F4B6C2", "bunny.nose": "#EE8E9E",
    "plush.blush": "#F2A0A0", "plush.pad": "#F3B4AE", "plush.eye": "#33241E", "plush.iris": "#4E2C1C", "plush.glow": "#A06A44",
    # each animal's eyes: a dark iris and the lighter colour that glows in its lower half
    "bear.iris": "#5A3216", "bear.glow": "#C08A3E", "cat.iris": "#2E5E34", "cat.glow": "#86C06A",
    "pig.iris": "#24476E", "pig.glow": "#79A9DA", "bunny.iris": "#7A2238", "bunny.glow": "#E07A96",
    # stitches and the accessories
    "plush.stitch": "#7A5A48", "otter.shell": "#F3B9B0", "pika.stem": "#7DB36A", "pika.bloom": "#F6D24A", "bear.bow": "#D9605A", "cat.collar": "#5B8FD0", "cat.bell": "#EBC24A",
    "pig.petal": "#FFFDF6", "pig.heart": "#F2C94C", "bunny.bow": "#A98BD8",
    # red panda, quokka, fennec
    "redpanda.fur": "#E08657", "redpanda.white": "#FFF8EE", "redpanda.limb": "#7A4334", "redpanda.belly": "#A0573D",
    "redpanda.ring": "#F7D9B4", "redpanda.nose": "#3A2620", "redpanda.iris": "#3A2015", "redpanda.glow": "#8A5030",
    "quokka.fur": "#A68B70", "quokka.light": "#C9B297", "quokka.inner": "#7E6450", "quokka.nose": "#3B2A22",
    "quokka.iris": "#2A1A12", "quokka.glow": "#7A5236",
    "fennec.fur": "#F2D7A6", "fennec.light": "#FFF5E4", "fennec.inner": "#F4B9B0", "fennec.nose": "#3A2A24",
    "fennec.tip": "#7A5A44", "fennec.iris": "#4A3016", "fennec.glow": "#C89040",
    # sea otter, koala, pika
    "otter.fur": "#8B6B55", "otter.head": "#DCC6A8", "otter.light": "#EFE2CC", "otter.nose": "#3A2A24",
    "otter.inner": "#6E5443", "otter.iris": "#2E1E14", "otter.glow": "#7A5236",
    "koala.fur": "#A7ACB2", "koala.light": "#F3F3F0", "koala.nose": "#3C3A40", "koala.iris": "#3A2C24",
    "koala.glow": "#8A6A50",
    "pika.fur": "#CDA57A", "pika.light": "#F2E0C4", "pika.nose": "#DD8E8E", "pika.inner": "#B08460",
    "pika.iris": "#2E1E14", "pika.glow": "#7A5236",
    # axolotl, arctic fox cub, pygmy hippo
    "axolotl.fur": "#F7B6C8", "axolotl.light": "#FDE3EA", "axolotl.gill": "#E26F92", "axolotl.iris": "#2A2030",
    "axolotl.glow": "#6A5A80",
    "arctic.fur": "#F4F3EE", "arctic.light": "#FFFFFF", "arctic.inner": "#EBC9C6", "arctic.nose": "#34302E",
    "arctic.tip": "#B4C3D2", "arctic.iris": "#2F5578", "arctic.glow": "#8FBADB",
    "hippo.fur": "#8F8B9C", "hippo.light": "#BDB7C6", "hippo.belly": "#CFC6CC", "hippo.inner": "#77738A",
    "hippo.nostril": "#55516A", "hippo.iris": "#33241C", "hippo.glow": "#80604A",
    # lion, tiger, giant panda, bald eagle, duck, dragon, three-banded armadillo, shark
    "lion.fur": "#EDBE6A", "lion.light": "#FBEBC8", "lion.mane": "#A9642C", "lion.nose": "#8A4A3A",
    "lion.iris": "#6A4212", "lion.glow": "#D49A3A",
    "tiger.fur": "#F39A3C", "tiger.light": "#FFF7EA", "tiger.stripe": "#3A2A22", "tiger.nose": "#D9777A",
    "tiger.iris": "#5A4A12", "tiger.glow": "#C8B03A",
    "gpanda.fur": "#FBFAF6", "gpanda.black": "#3A3836", "gpanda.patch": "#3A3836", "gpanda.iris": "#6A4A32", "gpanda.glow": "#A88A68",
    "eagle.fur": "#5E4634", "eagle.head": "#FBF9F2", "eagle.light": "#7A6048", "eagle.beak": "#F2B93A",
    "eagle.iris": "#8A6A10", "eagle.glow": "#F0D264",
    "duck.fur": "#FFD94E", "duck.light": "#FFEFA6", "duck.bill": "#F08A32", "duck.iris": "#2E2018",
    "duck.glow": "#7A5A3A",
    "dragon.fur": "#7CC47C", "dragon.light": "#A8DDA0", "dragon.belly": "#F5ECAE", "dragon.horn": "#FBF3DC",
    "dragon.wing": "#F2A65A", "dragon.nostril": "#3F7A48", "dragon.iris": "#8A4A10", "dragon.glow": "#F2B040",
    "armadillo.fur": "#D9B48E", "armadillo.light": "#F2DEC6", "armadillo.shell": "#A58562", "armadillo.band": "#7E6248",
    "armadillo.nose": "#C98A84", "armadillo.iris": "#2E1E14", "armadillo.glow": "#7A5236",
    "shark.fur": "#7FA6C6", "shark.light": "#F6F8FA", "shark.gill": "#4E7696", "shark.iris": "#20262E",
    "shark.glow": "#5A6E86",
    # tree frog
    "treefrog.fur": "#8CC56A", "treefrog.light": "#F4F3DC", "treefrog.inner": "#A9D88C", "treefrog.iris": "#33241C",
    "treefrog.glow": "#80604A",
    # the plush robots (the operator, 2026-11-11): Bip, Zap, Tec, Latinha
    "robot.screen": "#2A3042", "robot.metal": "#8E97A6", "robot.dark": "#4A4F5C",
    "robot.red": "#F0706A", "robot.green": "#6CCB8B", "robot.blue": "#58B6E6", "robot.yellow": "#FFD23F",
    "bip.fur": "#EEF1F2", "bip.accent": "#5AA9E6", "bip.led": "#7FE3F2",
    "zap.fur": "#7FA3C0", "zap.accent": "#FFD23F", "zap.led": "#FFE066",
    "tec.fur": "#7D8794", "tec.accent": "#4FC3B5", "tec.band": "#4A4F5C", "tec.led": "#7FF0D8",
    "lata.fur": "#F08A6B", "lata.accent": "#E9BC4A", "lata.led": "#FFF1BE",
    # the robots that stand for programming languages (the operator, 2026-11-11): Java, C, Python
    # no two alike: Java a white mug with red (the operator: "pode continuar branco"), C blue with white,
    # Python yellow with blue
    "java.fur": "#F3EDE4", "java.accent": "#E0533D", "java.led": "#FFB27A", "java.steam": "#D5DBE2",
    "java.bean": "#7A4A2A", "java.crease": "#3E2413",
    "c.fur": "#3E74C4", "c.accent": "#F1F5F9", "c.led": "#CFE8FF",
    "python.fur": "#FFCF3F", "python.accent": "#3776AB", "python.led": "#9FD0FF",
    # the robots that stand for AI assistants (the operator, 2026-11-11): Claude, ChatGPT
    "claude.fur": "#CC6B4A", "claude.accent": "#F4E9DA", "claude.ray": "#F2A65A", "claude.led": "#FFE2C2",
    "chatgpt.fur": "#19A383", "chatgpt.accent": "#F4F7F6", "chatgpt.led": "#D8FFF2",
}
m.COLOURS.update(COLOURS)

# One skeleton for the family: a huge head (head 3.6, over half the height), stubby legs and arms. Rest-pose joints
# (m): hips 0.12, chest 0.21, neck 0.34, head bone 0.43, shoulders 0.31 (x 0.11), hands 0.19, knees 0.07, ankles 0.03.
# The arm is 0.166 m from shoulder to wrist (arms 0.59; it was 0.104, arms 0.37, until 2026-11-12): at 0.104 it hid
# against the body at rest and was drawn up to five times as long to get a paw to the face.
BUILD = Build(height=0.7, head=3.6, torso=0.8, legs=0.18, arms=0.59, shoulders=1.0, hips=1.25)
# A short round body that sits low, almost on the ground, with the head resting on it (no neck): the legs are
# inside it and only the feet show, so the toy reads as one soft shape, not a jointed doll.
BODY = ((0.0, 0.15, 0.005), (0.185, 0.13, 0.155))
HEAD = ((0.0, 0.47, 0.012), (0.24, 0.212, 0.216))   # about two thirds of the height
# The face is a baby's: everything in the lower third of a big empty head, the eyes large, wide apart and low.
EYE_X, EYE_Y, EYE_W, EYE_H = 0.38, -0.2, 0.12, 0.17
# the ears, belly and tails below were drawn on a head and body of these sizes; hd()/bd() carry them to the above
_HEAD0 = ((0.0, 0.58, 0.01), (0.2, 0.178, 0.18))
_BODY0 = ((0.0, 0.27, 0.0), (0.165, 0.155, 0.14))
# a family stance under every pose: the head a little to one side, toes a little in, one foot a little ahead
STANCE = {"head.tilt_left_right": 10.0, "left_upper_leg.twist_in_out": 20.0, "right_upper_leg.twist_in_out": 20.0,
          "left_upper_leg.front_back": -12.0, "right_upper_leg.front_back": 4.0}
REST_HANDS = (0.125, 0.15, 0.14)  # resting paws on the sides of the tummy


@dataclass(frozen=True)
class Animal:
    key: str
    name: str
    fur: str        # material of body, head and limbs
    light: str      # belly, muzzle
    ears: str       # "round", "point", "flop", "long"
    muzzle: str     # "bear", "cat", "pig", "bunny"
    tail: str       # "ball", "long", "curl", "puff"
    eyes: str = "plush"  # its eye colours: "<eyes>.iris" and "<eyes>.glow"
    extra: str = ""      # its accessory: "bowtie", "collar", "flower", "bow"
    limb: str = ""       # arms and legs, when not the fur (the red panda's dark legs)
    belly: str = ""      # the tummy patch, when not `light`
    nose: str = ""       # the nose on a muzzle
    inner: str = ""      # inside the ears
    tail2: str = ""      # the tail's second colour: rings, or the tip
    foot: Optional[tuple[float, float, float]] = None  # its feet, when not the family's (the quokka's long feet)
    rest_mouth: str = "" # what a "flat" mouth is on this face (the quokka always smiles)
    marks: str = ""      # face markings: "panda" (white brow spots and cheeks)
    head: str = ""       # the head, when not the fur (the sea otter's pale face)
    whiskers: float = 0.0  # whiskers starting this far from the middle of the face (0 = none)
    ear: str = ""        # the ears, when not the fur (the giant panda's black ears)
    patch: str = ""      # a patch round each eye (the giant panda's); the lids take its colour
    stripes: str = ""    # stripes on the forehead, in this colour
    cheeks: str = ""     # three short lines on each cheek, in this colour (a tiger's stripes, a shark's gills)
    feet: str = ""       # the feet, when not the limbs' colour
    extras: tuple = ()   # parts of its own: "mane", "spikes", "wings", "shell", "dorsal"
    tail_k: float = 1.0  # a bushy tail's thickness and how far it swings out to the side (so it shows from the front)
    visor: str = ""      # a robot's screen, in this colour: the face is drawn on it in `led`, the lids take its colour
    led: str = ""        # what a robot's eyes, brows and mouth are lit in
    paw: str = ""        # hands and feet, when not the limbs' colour
    boxy: tuple = (0.0, 0.0)  # body and head as rounded boxes (mascots3d.Spec.boxy)


ANIMALS = {
    "bear": Animal("bear", "Bear Cub", "bear.fur", "bear.light", "round", "bear", "ball", "bear", "bowtie"),
    "cat": Animal("cat", "Kitten", "cat.fur", "cat.light", "point", "cat", "long", "cat", "collar", whiskers=0.52,
                  stripes="cat.stripe"),
    "pig": Animal("pig", "Piggy", "pig.fur", "pig.light", "flop", "pig", "curl", "pig", "flower"),
    "bunny": Animal("bunny", "Bunny", "bunny.fur", "bunny.light", "long", "bunny", "puff", "bunny", "bow"),
    # the three cutest in the consensus of cuteness lists (red panda, quokka, fennec fox)
    "redpanda": Animal("redpanda", "Red Panda", "redpanda.fur", "redpanda.white", "panda", "panda", "ringed",
                       "redpanda", limb="redpanda.limb", belly="redpanda.belly", nose="redpanda.nose",
                       inner="redpanda.fur", tail2="redpanda.ring", marks="panda", tail_k=1.45),
    "quokka": Animal("quokka", "Quokka", "quokka.fur", "quokka.light", "small", "grin", "thin", "quokka",
                     nose="quokka.nose", inner="quokka.inner", foot=(0.06, 0.036, 0.1), rest_mouth="smile"),
    "fennec": Animal("fennec", "Fennec", "fennec.fur", "fennec.light", "huge", "fox", "brush", "fennec",
                     nose="fennec.nose", inner="fennec.inner", tail2="fennec.tip"),
    # the next three of that consensus (sea otter, koala, pika)
    "otter": Animal("otter", "Sea Otter", "otter.fur", "otter.light", "tiny", "otter", "thick", "otter",
                    nose="otter.nose", inner="otter.inner", head="otter.head", extra="clam"),
    "koala": Animal("koala", "Koala", "koala.fur", "koala.light", "fluffy", "koala", "none", "koala",
                    nose="koala.nose", inner="koala.light"),
    "pika": Animal("pika", "Pika", "pika.fur", "pika.light", "pika", "pika", "none", "pika",
                   nose="pika.nose", inner="pika.inner", extra="sprig"),
    # and the next three (axolotl, arctic fox cub, pygmy hippo)
    "axolotl": Animal("axolotl", "Axolotl", "axolotl.fur", "axolotl.light", "gills", "axolotl", "thick", "axolotl",
                      inner="axolotl.gill", rest_mouth="smile"),
    "arcticfox": Animal("arcticfox", "Arctic Fox", "arctic.fur", "arctic.light", "fox", "fox", "brush", "arctic",
                        nose="arctic.nose", inner="arctic.inner", tail2="arctic.tip", tail_k=1.5),
    "hippo": Animal("hippo", "Pygmy Hippo", "hippo.fur", "hippo.light", "tiny", "hippo", "none", "hippo",
                    belly="hippo.belly", nose="hippo.nostril", inner="hippo.inner"),
    # asked for by the operator (2026-11-11)
    "lion": Animal("lion", "Lion", "lion.fur", "lion.light", "round", "bear", "long", "lion", nose="lion.nose",
                   tail2="lion.mane", extras=("mane",)),
    "tiger": Animal("tiger", "Tiger", "tiger.fur", "tiger.light", "round", "panda", "ringed", "tiger",
                    nose="tiger.nose", tail2="tiger.stripe", stripes="tiger.stripe", cheeks="tiger.stripe"),
    "panda": Animal("panda", "Panda", "gpanda.fur", "gpanda.fur", "round", "bear", "ball", "gpanda",
                    limb="gpanda.black", nose="gpanda.black", ear="gpanda.black", inner="gpanda.black",
                    patch="gpanda.patch"),
    "eagle": Animal("eagle", "Bald Eagle", "eagle.fur", "eagle.light", "none", "beak", "thick", "eagle",
                    nose="eagle.beak", head="eagle.head", tail2="eagle.head", feet="eagle.beak"),
    "duck": Animal("duck", "Duck", "duck.fur", "duck.light", "none", "bill", "ball", "duck", nose="duck.bill",
                   feet="duck.bill"),
    "dragon": Animal("dragon", "Dragon", "dragon.fur", "dragon.light", "horns", "dragon", "thick", "dragon",
                     belly="dragon.belly", nose="dragon.nostril", inner="dragon.horn", tail2="",
                     extras=("spikes", "wings")),
    "armadillo": Animal("armadillo", "Armadillo", "armadillo.fur", "armadillo.light", "fox", "fox", "thin",
                        "armadillo", nose="armadillo.nose", inner="armadillo.nose", extras=("shell",)),
    "shark": Animal("shark", "Shark", "shark.fur", "shark.light", "none", "shark", "thick", "shark",
                    cheeks="shark.gill", rest_mouth="smile", extras=("dorsal",)),
    # a plush frog for the family (Professor Frog, `frog`, is the older mascot in another style)
    "treefrog": Animal("treefrog", "Tree Frog", "treefrog.fur", "treefrog.light", "bumps", "axolotl", "none",
                       "treefrog", inner="treefrog.inner", rest_mouth="smile"),
    # the robots, asked for by the operator (2026-11-11; "eles nao precisam parecer brinquedos"): the family's
    # size and skeleton, but machines, not toys: a square head and body, a dark screen for a face whose eyes,
    # brows and mouth are lit, metal limbs, rivets, a neck ring, no blush and no paw pads. `inner` is the robot's
    # metal, `nose` its accent.
    "bip": Animal("bip", "Bip", "bip.fur", "bip.fur", "antenna", "robot", "none", extra="core",
                  inner="robot.metal", nose="robot.red", tail2="bip.accent", limb="robot.metal", paw="bip.accent",
                  visor="robot.screen", led="bip.led", rest_mouth="smile", extras=("ring",), boxy=(0.6, 0.55)),
    "zap": Animal("zap", "Zap", "zap.fur", "zap.fur", "antennae", "robot", "none", extra="buttons",
                  inner="robot.metal", nose="zap.accent", limb="robot.metal", paw="zap.accent",
                  visor="robot.screen", led="zap.led", extras=("ring",), boxy=(0.6, 0.55)),
    "tec": Animal("tec", "Tec", "tec.fur", "tec.fur", "phones", "robot", "none", extra="gauge",
                  inner="tec.band", nose="tec.accent", limb="robot.metal", paw="tec.accent",
                  visor="robot.screen", led="tec.led", extras=("ring",), boxy=(0.6, 0.55)),
    "lata": Animal("lata", "Latinha", "lata.fur", "lata.fur", "dome", "robot", "none", extra="bars",
                   inner="lata.accent", nose="lata.led", limb="robot.metal", paw="lata.accent",
                   visor="robot.screen", led="lata.led", rest_mouth="smile", extras=("ring",),
                   boxy=(0.72, 0.62)),
    # Robots that stand for programming languages (the operator, 2026-11-11). None wears a language's logo:
    # Java is a white coffee mug with red (steam, a handle, a bean), C a plain strict blue box with a pointer's asterisk
    # and its letter, Python yellow and blue with a snake coiled on its head, a snake's tail and indented lines.
    "java": Animal("java", "Java", "java.fur", "java.fur", "steam", "robot", "none", extra="bean",
                   inner="robot.metal", nose="java.steam", tail2="java.accent", limb="robot.metal",
                   paw="java.accent", visor="robot.screen", led="java.led", rest_mouth="smile",
                   extras=("ring", "handle"), boxy=(0.72, 0.62)),
    "c": Animal("c", "C", "c.fur", "c.fur", "star", "robot", "none", extra="letterc",
                inner="robot.metal", nose="robot.yellow", tail2="c.accent", limb="robot.metal", paw="c.accent",
                visor="robot.screen", led="c.led", extras=("ring",), boxy=(0.5, 0.5)),
    "python": Animal("python", "Python", "python.fur", "python.fur", "coil", "robot", "thick", extra="indent",
                     inner="robot.metal", nose="python.accent", tail2="python.accent", limb="robot.metal",
                     paw="python.accent", visor="robot.screen", led="python.led", rest_mouth="smile",
                     extras=("ring",), boxy=(0.6, 0.55)),
    # Robots that stand for AI assistants (the operator, 2026-11-11), again without a logo: each in its
    # product's colour, with a speech bubble on its chest. Claude is warm clay and cream with a crest of rays
    # and lines of text in its bubble; ChatGPT is green and white with a ring antenna and three dots in its bubble.
    "claude": Animal("claude", "Claude", "claude.fur", "claude.fur", "crest", "robot", "none", extra="lines",
                     inner="robot.metal", nose="claude.ray", tail2="claude.accent", limb="robot.metal",
                     paw="claude.accent", visor="robot.screen", led="claude.led", rest_mouth="smile",
                     extras=("ring",), boxy=(0.66, 0.6)),
    "chatgpt": Animal("chatgpt", "ChatGPT", "chatgpt.fur", "chatgpt.fur", "loop", "robot", "none", extra="dots",
                      inner="robot.metal", nose="chatgpt.accent", tail2="chatgpt.accent", limb="robot.metal",
                      paw="chatgpt.accent", visor="robot.screen", led="chatgpt.led", rest_mouth="smile",
                      extras=("ring",), boxy=(0.6, 0.55)),
}
ROBOTS = ("bip", "zap", "tec", "lata", "java", "c", "python", "claude", "chatgpt")

# Each animal's own silhouette and posture, on the family's proportions: the body's width, height and depth (times
# BODY's), where its resting paws go, and how far its head tilts (degrees; the sign is the side).
SHAPES = {
    "bear": (1.1, 1.0, 1.05), "cat": (0.84, 1.08, 0.9), "pig": (1.12, 1.0, 1.08), "bunny": (0.9, 1.06, 0.94),
    "redpanda": (1.0, 1.05, 1.0), "quokka": (1.18, 1.02, 1.12), "fennec": (0.84, 1.02, 0.9),
    "otter": (0.9, 1.22, 0.95), "koala": (1.22, 1.0, 1.08), "pika": (1.0, 1.0, 1.0),
    "axolotl": (0.9, 1.1, 0.9), "arcticfox": (0.9, 1.0, 0.95), "hippo": (1.28, 1.05, 1.18),
    "lion": (1.06, 1.05, 1.05), "tiger": (1.0, 1.08, 1.0), "panda": (1.22, 1.06, 1.12),
    "eagle": (0.95, 1.18, 1.0), "duck": (0.98, 1.22, 1.08), "dragon": (1.05, 1.12, 1.05),
    "armadillo": (1.1, 1.0, 1.1), "shark": (0.98, 1.18, 1.0),
}
PAWS = {"tummy": (0.175, 0.14, 0.1),  # at the sides of the tummy, clear of the pale patch
        "together": (0.045, 0.16, 0.19), "up": (0.14, 0.27, 0.2), "down": None}
POSTURE = {  # (paws, head tilt); no one rests with paws "together": arms crossing the pale tummy cut a collar into it
    "bear": ("up", 8), "cat": ("down", -12), "pig": ("tummy", 12), "bunny": ("tummy", -6),
    "redpanda": ("up", -10), "quokka": ("up", 10), "fennec": ("down", 14), "otter": ("down", -8),
    "koala": ("tummy", 14), "pika": ("tummy", 6), "axolotl": ("down", -10), "arcticfox": ("down", 10),
    "hippo": ("down", -6), "lion": ("tummy", 8), "tiger": ("down", -10), "panda": ("down", 12),
    "eagle": ("down", -5), "duck": ("down", 10), "dragon": ("tummy", -8), "armadillo": ("down", 8),
    "shark": ("down", -12),
}


SHAPES.update({"bip": (0.95, 1.0, 0.95), "zap": (0.84, 1.1, 0.88), "tec": (1.06, 1.0, 1.0), "lata": (0.9, 1.16, 0.95)})
SHAPES.update({"java": (0.98, 1.08, 1.0), "c": (0.95, 1.0, 0.95), "python": (0.88, 1.12, 0.9)})
SHAPES.update({"claude": (0.98, 1.04, 0.98), "chatgpt": (0.98, 1.04, 0.98)})
POSTURE.update({"claude": ("down", 9), "chatgpt": ("down", -9)})
POSTURE.update({"java": ("down", 8), "c": ("down", -4), "python": ("down", -10)})
POSTURE.update({"bip": ("down", 8), "zap": ("down", -10), "tec": ("down", 10), "lata": ("down", -6)})  # the chest panel shows
# A robot's screen: a rounded rectangle on the front of its head, VISOR_OUT (a share of the head's depth) proud of
# it. (half-width and half-height as shares of the head's radii, the height of its middle, how square its corners.)
VISOR, VISOR_OUT = (0.64, 0.5, -0.22, 0.35), 0.034


def _body_of(key: str):
    kx, ky, kz = SHAPES.get(key, (1.0, 1.0, 1.0))
    rx, ry, rz = BODY[1][0] * kx, BODY[1][1] * ky, BODY[1][2] * kz
    # it sits on the ground whatever its height; never lower than BODY, or a gap opens under the head
    return ((0.0, ry + 0.02, BODY[0][2]), (rx, ry, rz))


for _a in ANIMALS.values():
    _paws, _tilt = POSTURE.get(_a.key, ("tummy", 10))
    m.SPECS[_a.key] = m.Spec(_a.key, BUILD, (*_body_of(_a.key), _a.fur), face="head", head=(*HEAD, _a.head or _a.fur),
                             limb=_a.limb or _a.fur, arm_r=0.037, leg_r=0.056, merge=True, foot=_a.foot or (0.066, 0.04, 0.078),
                             splay=0.55, rest_hands=PAWS[_paws], foot_m=_a.feet, paw=_a.paw, boxy=_a.boxy,
                             arm_taper=(1.0, 0.96, 0.92), leg_taper=(1.1, 1.0, 0.9), hand=1.5,
                             pad="robot.dark" if _a.visor else "plush.pad", stance={**STANCE, "head.tilt_left_right": float(_tilt)},
                             reach=0.25, stretch=1.5)  # a paw goes as near the face as stubby arms allow
    m.NAMES[_a.key] = _a.name


class SoftPencil(PencilFlat):
    """The pencil laid down fuller and smoother, so pastels stay clean instead of greying with paper tooth."""

    def add(self, stage: Stage) -> None:
        e = stage.effects.add_effect(id="pencil-3d", type="shader", src=str(SHADER))
        for k, v in dict(angle=1.05, spacing=3.4, density=1.0, tooth=0.04, seed=1.0, bydark=0.0).items():
            e.add_param(name=k, value=str(v))
        group = stage.group("flat", ["pencil-3d"])

        def paint(skin, leaf):
            material = stage.material_of(skin.name, skin.own, leaf)
            color = self.color(skin.name, material, leaf)
            return f"flat-{skin.name.replace('.', '-')}{stage.aimed(leaf)}", {"baseColor": color, "unlit": True}, None

        for index, leaf in enumerate(stage.solids):
            stage.coat(group, leaf, index, "flat-", paint, False)


from srlocations import Sky as _Sky  # noqa: E402


@dataclass
class UnseenSky(_Sky):
    """A sky that lights the location but is not drawn behind it."""

    def attributes(self):
        return {**super().attributes(), "environmentVisible": False}


@dataclass
class SoftShade(Cel):
    """Light and shade that roll in softly (Cel's two tones, with a smooth edge): the volume of a soft toy."""
    soft: float = 0.18

    def relight(self, light):
        # The sky keeps its strength but its ground half goes dark, so what faces down (under the head, the tummy,
        # the arms) rolls into shade. In this pass it lights without being drawn: drawn, its dark ground showed
        # behind the figures below the horizon (and Cel's dimmed fill had greyed the whole frame).
        from dataclasses import fields
        from srlocations import Sky
        if not isinstance(light, Sky):
            return super().relight(light)
        kept = {f.name: getattr(light, f.name) for f in fields(light) if f.init}
        return UnseenSky(**{**kept, "ground": "#5a5a5a"})

    def add(self, stage: Stage) -> None:
        e = stage.effects.add_effect(id="soft-shade", type="shader", src=str(SOFT_SHADE))
        r, g, b = channels(self.shade)
        for k, v in dict(cut=self.cut, soft=self.soft, shadeR=r, shadeG=g, shadeB=b).items():
            e.add_param(name=k, value=str(v))
        self.tones(stage, stage.group("cel", ["soft-shade"], blend="multiply"))


def _contacts_last(stage: Stage):
    """The stage's solids as (everything but contact shadows, the contact shadows). Every pass of the look numbers
    the solids in this one order, so a solid has the same index in each."""
    plain = [leaf for leaf in stage.solids if not isinstance(leaf.item, m.Contact)]
    return plain, [leaf for leaf in stage.solids if isinstance(leaf.item, m.Contact)]


class _NoContact:
    """A pass that does not draw contact shadows (they are shade, not colour, and take no ink)."""

    def add(self, stage: Stage) -> None:
        kept = stage.solids
        stage.solids = _contacts_last(stage)[0]
        try:
            super().add(stage)
        finally:
            stage.solids = kept


class PlushFill(_NoContact, SoftPencil):
    pass


class PlushLine(_NoContact, InkByMaterial):
    pass


@dataclass
class ContactShade(SoftShade):
    """SoftShade, and under each figure its contact shadow (mascots3d.Contact), drawn into the same shade pass: an
    unlit grey there comes out as the shade colour, full under the middle and half as much round the rim. Being in
    the pass the figures are in, it is hidden behind them where it should be, and it multiplies over whatever the
    figure stands on (paper, a step)."""
    TONES = {"plush.contact": "#8C8C8C", "plush.contact-soft": "#C8C8C8"}

    def tones(self, stage: Stage, group) -> None:
        kept = stage.solids
        plain, contacts = _contacts_last(stage)
        stage.solids = plain
        try:
            super().tones(stage, group)
        finally:
            stage.solids = kept
        for i, leaf in enumerate(contacts):
            name = leaf.item.material
            tone = stage.material(f"contact-{name.replace('.', '-')}", baseColor=self.TONES.get(name, "#C8C8C8"), unlit=True)
            stage.compiler.draw(group, leaf, len(plain) + i, "cel-", tone, shadow=False)


@dataclass
class Glow(Pass):
    """Light round what is lit: every part whose material ends in ".led" (a robot's eyes, mouth, status lights) is
    drawn again, blurred, and added over the picture. Everything else is drawn black in the same pass, so a lit
    part behind a head stays hidden and adds nothing. A shot with nothing lit gets no pass at all."""
    radius: float = 7.0
    opacity: float = 0.85

    def add(self, stage: Stage) -> None:
        plain = _contacts_last(stage)[0]
        if not any(str(leaf.item.material).endswith(".led") for leaf in plain):
            return
        group = stage.group("glow", [stage.effect("glow-blur", "blur", radius=self.radius)], blend="screen",
                            opacity=self.opacity)
        dark = stage.material("glow-none", baseColor="#000000", unlit=True)
        for index, leaf in enumerate(plain):
            name = str(leaf.item.material)
            lit = name.endswith(".led")
            chosen = stage.material(f"glow-{name.replace('.', '-')}", unlit=True,
                                    baseColor=stage.material_of(name, leaf=leaf).color) if lit else dark
            stage.compiler.draw(group, leaf, index, "glow-", chosen, shadow=False)


def look() -> Look:
    """The plush look: soft fill, soft shade (volume) with a contact shadow under each figure, the glow of what is
    lit (robots), and a thinner, warm dark-brown line with more wobble."""
    return Look([PlushFill(), ContactShade(cut=0.8, shade="#D8C4C4", soft=0.12), Glow(),
                 PlushLine(color="#6B4A36", width=2.6, vary=0.3, wobble=1.0)],
                sky=paper.marker.PAPER[:7], name="plush.paper")


def _carry_to(old, new):
    (c0, r0), (c1, r1) = old, new

    def to(p):
        return tuple(c1[i] + (p[i] - c0[i]) * r1[i] / r0[i] for i in range(3))
    return to, sum(r1[i] / r0[i] for i in range(3)) / 3


hd, KH = _carry_to(_HEAD0, HEAD)
bd, KB = _carry_to(_BODY0, BODY)


def _ellipsoid_on(centre, radii):
    """Points on an ellipsoid's front, in design space: on(fx, fy, out)."""
    C, R = centre, radii

    def on(fx, fy, out=0.0):
        z = math.sqrt(max(0.0, 1 - fx * fx - fy * fy))
        return (C[0] + fx * R[0], C[1] + fy * R[1], C[2] + (z + out) * R[2])
    return on


# Upper lids per brow: (where the lid's edge cuts the eye, -1 bottom .. 1 top; slant in degrees, + = inner side down)
LIDS = {"angry": (0.22, 26.0), "worried": (0.3, -26.0), "flat": None, "raised": None, "none": None,
        "arched": None}  # arched: one brow up and the eye under it open (skeptic lowers a lid on that eye)


def eyes(on, limb, stroke, R, e, colour: str = "plush", lid_fur: str = "dev.skin", shut: float = 0.0,
         scale: float = 1.0, shut_each: tuple = (0.0, 0.0), screen: bool = False) -> None:
    """Eyes that act: a glossy iris (dark, warmer below), pupil and shines, cut by lids of fur. The upper lid's height
    and slant come from the brows (angry: down at the nose; worried: down at the outside), a half-open eye from
    `eyes="half"`; a smile pushes the lower lid up (smiling eyes); closed eyes are arches; wide eyes have small
    pupils; sad eyes are wet and one sheds a tear. `shut` lowers the upper lid (0 open, 1 shut: the frames either
    side of a blink); `scale` sizes the eyes; the eyes shift a little the way they look. On a `screen` (a robot's
    face) there are no lids: what a lid would cover, the lit eye loses in height, so it flattens as it shuts."""
    lx, ly = (max(-1.0, min(1.0, v)) for v in e.look)
    both = shut                                               # each eye adds its own (a wink): (left, right)
    limb0 = limb
    smiling = e.mouth in ("smile", "smug")
    sad = e.brows == "worried" and e.mouth in ("frown", "wavy")
    for sx in (-1, 1):
        fx, fy = sx * EYE_X + 0.04 * lx, EYE_Y - 0.035 * ly
        shut = min(1.0, both + shut_each[1 if sx > 0 else 0])
        # every part of an eye is turned to lie on the head where the eye is (so far round, a flat part would slant)
        turn = EYE_TURN * math.degrees(math.atan2(fx, math.sqrt(max(0.05, 1 - fx * fx - fy * fy))))
        limb = (lambda flat: lambda *a, **k: flat(*a, **{"yaw": turn, **k}))(limb0)
        if e.eyes == "closed" or shut >= 0.9:  # happy arches when smiling, a soft downward curve otherwise
            up = 1.0 if smiling else -0.6
            stroke("eye/closed", [on(fx + (i - 4) / 4 * 0.13, fy + up * 0.06 * (1 - ((i - 4) / 4) ** 2), 0.01)
                                  for i in range(9)], 0.0055)
            continue
        if e.eyes == "spiral":
            m.spiral(on, stroke, fx, fy, 0.13, 0.003)
            continue
        # the upper lid
        lid = LIDS.get(e.brows)
        if e.brows == "skeptic":
            lid = (0.05, -6.0) if sx > 0 else None
        if e.eyes == "half":
            lid = (0.08, 0.0) if lid is None else (min(lid[0], 0.08), lid[1])
        if e.eyes == "wide" and lid is not None:
            lid = (max(lid[0], 0.72), lid[1] * 0.6)
        if shut > 0.25:  # the lid comes down over the eye (a lid barely lowered reads as a frown: not drawn)
            cut = 1.0 - 2.0 * shut
            lid = (cut, 0.0) if lid is None else (min(lid[0], cut), lid[1])
        size = {"wide": 1.15, "squint": 0.8}.get(e.eyes, 1.0) * scale
        W, H = EYE_W * size, EYE_H * size
        if screen:               # a picture of an eye on a screen: it flattens, and nothing dark is laid over it
            if lid is not None:
                H *= max(0.12, min(1.0, (1.0 + lid[0]) / 2))
            lid = None
        # a simple eye reads best: one dark oval and one small shine (no iris, pupil or second reflection)
        limb("eye", on(fx, fy, -0.02), (W * R.x, H * R.y, 0.05 * R.z), "plush.eye")
        px = fx + max(-0.2, min(0.2, lx * 0.2 + (0.18 if e.eyes == "side" else 0.0))) * W  # the shine follows the look
        py = fy - ly * 0.2 * H
        big = 0.8 if e.eyes == "wide" else 1.0
        # a shine lies on the eye, so none is drawn above the upper lid's edge (it would poke through the fur)
        edge = fy + (lid[0] - 0.2) * H if lid is not None else 9.0

        def glint(gx, gy, rx, ry, rz, samples=(8, 6)):
            if gy + ry < edge:
                limb("eye-shine", on(gx, gy, 0.032), (rx * W * R.x, ry * R.y, rz * R.z), "dev.white", samples=samples)

        glint(px - 0.3 * W, py + 0.36 * H, 0.3 * big, 0.24 * big * H, 0.014, (10, 8))
        if sad:  # wet eyes: a line of light along the bottom, and a tear on one side
            limb("eye-shine", on(fx, fy - 0.68 * H, 0.03), (0.55 * W * R.x, 0.09 * H * R.y, 0.01 * R.z), "dev.white",
                 samples=(14, 8))
            if sx > 0 and e.mouth == "frown":
                limb("tear", on(fx + 0.55 * W, fy - 1.45 * H, 0.03), (0.035 * R.x, 0.055 * R.y, 0.025 * R.z),
                     "m.sweat", samples=(10, 8))
        # Lids are fur in the head's ink group ("head/..."): no outline of their own, only a line where they cut
        # the eye. They sit at the eye's depth (the head curves back above and below it).
        ez = on(fx, fy, 0.0)[2]
        if lid is not None:
            cut, slant = lid
            tall = max(0.45, (1.08 - cut) / 2)          # a low lid is taller, so no eye shows above it
            x, y, _z = on(fx, fy + cut * H + tall * H)  # low enough to leave the brows in front
            limb("head/lid", (x, y, ez - 0.03 * R.z), (1.3 * W * R.x, tall * H * R.y, 0.085 * R.z), lid_fur,
                 roll=slant * sx * LID_ROLL, samples=(18, 12))
        # the lower lid, pushed up by a smile
        if smiling and not screen and e.eyes not in ("wide", "half"):
            x, y, _z = on(fx, fy - 0.4 * H - 0.5 * H)
            limb("head/lid-low", (x, y, ez - 0.03 * R.z), (1.35 * W * R.x, 0.5 * H * R.y, 0.085 * R.z), lid_fur,
                 samples=(18, 12))


EYE_TURN = 1.0  # which way a positive yaw turns a part on this skeleton
LID_ROLL = 1.0  # which way a positive roll turns a lid on this skeleton (measured: see the yell/worried tiles)


# muzzles that stand out of the face: ((fy, out) of the centre, radii (shares of the head's), nose radii, nose fy)
MUZZLES = {
    "bear": ((-0.42, -0.3), (0.36, 0.27, 0.42), (0.03, 0.02, 0.02), 0.42),
    "panda": ((-0.43, -0.36), (0.5, 0.29, 0.44), (0.026, 0.018, 0.018), 0.4),  # wide: white out to the cheeks
    "quokka": ((-0.4, -0.3), (0.3, 0.27, 0.46), (0.028, 0.02, 0.02), 0.45),
    "otter": ((-0.42, -0.3), (0.42, 0.27, 0.42), (0.036, 0.024, 0.022), 0.42),  # broad, with a big nose
    "hippo": ((-0.44, -0.3), (0.86, 0.46, 0.5), (0.024, 0.02, 0.01), 0.45),  # very wide, two clear nostrils
    "dragon": ((-0.42, -0.3), (0.4, 0.28, 0.5), (0.012, 0.01, 0.008), 0.5),  # a round snout with nostrils
    "fox": ((-0.4, -0.26), (0.22, 0.19, 0.52), (0.022, 0.017, 0.02), 0.3),  # a fine pointed snout
}


WHISKER_X = (0.2, 0.42)       # where a whisker starts (beside the nose) and ends (before the blush), share of the face
WHISKER_Y = (-0.42, -0.5)     # the upper whisker at the nose's height, the lower one at the mouth's

ICONS = ("heart", "question", "exclaim", "dots")   # what a robot's screen can show in place of its face


def icon(on, stroke, name: str, material: str) -> None:
    """A picture lit on a robot's screen (MascotFigure.icon), drawn in the screen's own shares."""
    def line(points, r=0.0062):
        stroke("icon/line", [on(x, y, 0.012) for x, y in points], r, material)

    def dot(x, y, r=0.009):
        line([(x - 0.004, y), (x + 0.004, y)], r)

    if name == "heart":
        line([(0.019 * 16 * math.sin(t) ** 3,
               -0.27 + 0.019 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)))
              for t in (2 * math.pi * k / 40 for k in range(41))])
    elif name == "question":
        line([(0.17 * math.cos(math.radians(d)), -0.07 + 0.17 * math.sin(math.radians(d))) for d in range(165, -75, -15)]
             + [(0.0, -0.3), (0.0, -0.4)])
        dot(0.0, -0.57)
    elif name == "exclaim":
        line([(0.0, 0.1), (0.0, -0.38)], 0.0085)
        dot(0.0, -0.57)
    else:  # dots: it is thinking, or waiting
        for x in (-0.26, 0.0, 0.26):
            dot(x, -0.26, 0.011)


def build(fig: m.MascotFigure, frames, body, head, put) -> list:
    """The face, ears, belly and tail of one plush animal (mascots3d.BUILDERS hook)."""
    a, e = ANIMALS[fig.who], fig.expression
    hc, hr, _hm = fig.spec.head
    on, limb, R = fig._face(head, hc, hr, put)
    stroke, looks = fig._stroke, fig.looks

    class Ear:
        """The head's carry with one ear swung about its root: it leans out (fig.ear_left / ear_right, degrees) and
        back (fig.ear_back). sx = +1 is the figure's right ear."""

        def __init__(self, sx, root=None):
            self.pivot = hd(root or (sx * 0.11, 0.68, 0.0))
            self.out = math.radians(fig.ear_right if sx > 0 else fig.ear_left) * sx
            self.back = math.radians(fig.ear_back)
            self.scale, self.basis, self.vec = head.scale, head.basis, head.vec

        def point(self, p):
            dx, dy, dz = (p[i] - self.pivot[i] for i in range(3))
            # an ear bends: a point takes more of the angle the further it is from the root (a long ear curves)
            g = min(1.6, 0.35 + math.sqrt(dx * dx + dy * dy + dz * dz) / 0.12)
            ca, sa = math.cos(self.out * g), math.sin(self.out * g)
            cb, sb = math.cos(self.back * g), math.sin(self.back * g)
            x, y = dx * ca + dy * sa, -dx * sa + dy * ca      # lean out: the tip goes sideways
            y, z = y * cb + dz * sb, dz * cb - y * sb         # lean back: the tip goes behind
            return head.point((self.pivot[0] + x, self.pivot[1] + y, self.pivot[2] + z))

    ear = [head]  # what carries the ears being built: an Ear inside the ears' loop, the head itself after it

    def flat_tube(name, p0, p1, r0, r1, material, deep=0.38):  # an ear: a tapered tube flattened front to back
        return tube(name, ear[0].point(hd(p0)), ear[0].point(hd(p1)), r0 * KH, r1 * KH, material,
                    ref=head.vec((1, 0, 0)), wide=1.0, deep=deep, looks=looks, samples=(14, 18))

    def hput(name, p, r, material, samples=(20, 14)):  # a part drawn on the old head, carried to this one
        put(ear[0], name, hd(p), tuple(x * KH for x in r), material, m.IDENTITY, samples)

    bd, KB = _carry_to(_BODY0, fig.spec.body[:2])  # this animal's own body

    def bput(name, p, r, material, samples=(20, 14)):
        put(body, name, bd(p), tuple(x * KB for x in r), material, m.IDENTITY, samples)

    # ears
    def side(name, p, r, material, samples=(16, 12)):  # a part fixed to the head (it does not swing with an ear)
        put(head, name, hd(p), tuple(x * KH for x in r), material, m.IDENTITY, samples)

    for sx in (-1, 1):
        ear[0] = Ear(sx, (0.0, 0.75, 0.0) if a.ears in ("antenna", "steam", "star", "coil", "crest", "loop") else None)
        if a.ears == "crest":  # a rising sun on top of the head: a half disc and seven rays
            if sx > 0:
                hput("sun/disc", (0.0, 0.752, 0.0), (0.06, 0.04, 0.03), a.nose, samples=(20, 12))
                for i, deg in enumerate(range(-75, 76, 25)):
                    sn, cs = math.sin(math.radians(deg)), math.cos(math.radians(deg))
                    long_ = 0.04 if i % 2 == 0 else 0.028
                    p0 = (0.08 * sn, 0.752 + 0.058 * cs, 0.0)
                    fig._extra.append(flat_tube(f"ray_{i}/ray", p0, (p0[0] + long_ * sn, p0[1] + long_ * cs, 0.0),
                                                0.0085, 0.0085, a.nose, deep=1.0))
            continue
        if a.ears == "loop":  # a ring standing on a short stalk
            if sx > 0:
                fig._extra.append(flat_tube("antenna/stalk", (0.0, 0.745, 0.0), (0.0, 0.805, 0.0), 0.009, 0.009,
                                            a.inner, deep=1.0))
                big, thin = 0.04 * KH, 0.0115 * KH
                fig._extra.append(m.Limb(
                    x=f"({big:.5f}+{thin:.5f}*cos(v))*cos(u)", y=f"({big:.5f}+{thin:.5f}*cos(v))*sin(u)",
                    z=f"-{thin:.5f}*sin(v)", u=(0, 360), v=(0, 360), samples=(32, 8), closed=(True, True),
                    radii=(big + thin, big + thin, thin), at=ear[0].point(hd((0.0, 0.852, 0.0))),
                    basis=head.basis(m.IDENTITY), name="loop/loop", material=a.nose, casts_shadow=False,
                    looks=looks))
            continue
        if a.ears == "steam":  # a mug of coffee: three wisps of steam rising from the top of the head
            if sx > 0:
                for i, x0 in enumerate((-0.062, 0.0, 0.062)):
                    tall = 0.1 if i == 1 else 0.075
                    pts = [(x0 + 0.013 * math.sin(math.radians(k * 60 + i * 120)), 0.772 + tall * k / 6, 0.0)
                           for k in range(7)]
                    for k, (p0, p1) in enumerate(zip(pts, pts[1:])):
                        fig._extra.append(flat_tube(f"steam_{i}/wisp", p0, p1, 0.0085 - 0.0007 * k,
                                                    0.0085 - 0.0007 * (k + 1), a.nose, deep=1.0))
            continue
        if a.ears == "star":  # C: a bolt at each side, and on the antenna a pointer's asterisk
            side(f"bolt_{sx}/bolt", (sx * 0.2, 0.585, 0.0), (0.026, 0.04, 0.04), a.tail2)
            side(f"boltcap_{sx}/cap", (sx * 0.226, 0.585, 0.0), (0.012, 0.022, 0.022), a.inner, (12, 10))
            if sx > 0:
                fig._extra.append(flat_tube("antenna/stalk", (0.0, 0.745, 0.0), (0.0, 0.84, 0.0), 0.009, 0.009,
                                            a.inner, deep=1.0))
                for deg in (90, 30, 150):
                    dx, dy = 0.034 * math.cos(math.radians(deg)), 0.034 * math.sin(math.radians(deg))
                    fig._extra.append(flat_tube("star/arm", (-dx, 0.872 - dy, 0.0), (dx, 0.872 + dy, 0.0), 0.0085,
                                                0.0085, a.nose, deep=1.0))
            continue
        if a.ears == "coil":  # Python: a snake coiled on top of the head, its own head raised
            if sx > 0:
                pts = []
                for k in range(0, 29):  # two turns and a third, each smaller and on top of the last
                    t = math.radians(-90 + k * 30)
                    r = 0.064 - 0.0014 * k
                    pts.append((r * math.cos(t), 0.77 + 0.0021 * k, r * 0.85 * math.sin(t)))
                pts += [(0.0, 0.845, 0.012), (0.0, 0.868, 0.03)]  # the neck rises from the middle
                for k, (p0, p1) in enumerate(zip(pts, pts[1:])):
                    fig._extra.append(flat_tube("snake/coil", p0, p1, 0.0135, 0.0135, a.nose, deep=1.0))
                hput("snake/head", (0.0, 0.876, 0.046), (0.027, 0.021, 0.033), a.nose, samples=(16, 12))
                for ex in (-1, 1):
                    hput("snakeeye/eye", (ex * 0.019, 0.884, 0.06), (0.0055, 0.0065, 0.0055), "robot.dark",
                         samples=(8, 6))
                fig._extra.append(flat_tube("tongue/tongue", (0.0, 0.87, 0.076), (0.0, 0.864, 0.098), 0.003,
                                            0.002, "robot.red", deep=1.0))
            continue
        if a.ears == "antenna":  # a robot: a bolt at each side of the head and one antenna on top, which springs
            side(f"bolt_{sx}/bolt", (sx * 0.2, 0.585, 0.0), (0.026, 0.04, 0.04), a.tail2)
            side(f"boltcap_{sx}/cap", (sx * 0.226, 0.585, 0.0), (0.012, 0.022, 0.022), a.inner, (12, 10))
            if sx > 0:
                fig._extra.append(flat_tube("antenna/stalk", (0.0, 0.745, 0.0), (0.0, 0.85, 0.0), 0.009, 0.009,
                                            a.inner, deep=1.0))
                hput("bulb/ball", (0.0, 0.868, 0.0), (0.027, 0.027, 0.027), a.nose, samples=(16, 12))
        elif a.ears == "antennae":  # a robot: two antennae at the corners of the head, a ball on each
            fig._extra.append(flat_tube(f"antenna_{sx}/stalk", (sx * 0.11, 0.735, 0.0), (sx * 0.165, 0.845, 0.0),
                                        0.008, 0.008, a.inner, deep=1.0))
            hput(f"bulb_{sx}/ball", (sx * 0.173, 0.861, 0.0), (0.024, 0.024, 0.024), a.nose, samples=(16, 12))
        elif a.ears == "phones":  # a robot: headphones, a cup at each side and a band over the (square) head
            side(f"phone_{sx}/cup", (sx * 0.205, 0.585, 0.0), (0.036, 0.07, 0.07), a.nose, (18, 14))
            if sx > 0:
                e_, (hx_, hy_, hz_), (rx_, ry_, _rz) = a.boxy[1] or 1.0, HEAD[0], HEAD[1]
                arc = []
                for t in range(-88, 89, 8):
                    st, ct = math.sin(math.radians(t)), math.cos(math.radians(t))
                    arc.append((hx_ + 1.035 * rx_ * math.copysign(abs(st) ** e_, st), hy_ + 1.035 * ry_ * ct ** e_, hz_))
                for p0, p1 in zip(arc, arc[1:]):
                    fig._extra.append(tube("band/seg", head.point(p0), head.point(p1), 0.012 * KH, 0.012 * KH,
                                           a.inner, looks=looks, samples=(10, 12)))
        elif a.ears == "dome":  # a robot: a lamp on top of the head
            if sx > 0:
                side("lampbase/base", (0.0, 0.752, 0.0), (0.05, 0.016, 0.05), a.inner, (18, 10))
                side("lamp/lamp", (0.0, 0.768, 0.0), (0.036, 0.034, 0.036), a.nose, (18, 12))
        elif a.ears == "round":
            hput(f"ear_{sx}/ear", (sx * 0.135, 0.71, -0.01), (0.068, 0.066, 0.034), a.ear or a.fur, samples=(20, 12))
            hput(f"ear_{sx}/inner", (sx * 0.135, 0.705, 0.012), (0.042, 0.04, 0.018), a.inner or a.light,
                 samples=(16, 10))
        elif a.ears == "point":
            fig._extra.append(flat_tube(f"ear_{sx}/ear", (sx * 0.1, 0.66, 0.0), (sx * 0.165, 0.81, 0.0), 0.058,
                                        0.01, a.fur))
            fig._extra.append(flat_tube(f"ear_{sx}/inner", (sx * 0.105, 0.68, 0.016), (sx * 0.152, 0.775, 0.012),
                                        0.032, 0.008, "cat.nose", deep=0.3))
        elif a.ears == "flop":
            fig._extra.append(flat_tube(f"ear_{sx}/ear", (sx * 0.12, 0.715, 0.0), (sx * 0.175, 0.69, 0.12), 0.056,
                                        0.012, a.fur, deep=0.32))  # floppy: up and out, then forward and down
        elif a.ears == "panda":  # rounded triangles, white at the rim, fur inside
            fig._extra.append(flat_tube(f"ear_{sx}/ear", (sx * 0.11, 0.69, -0.005), (sx * 0.17, 0.8, -0.005), 0.062,
                                        0.036, a.light))
            fig._extra.append(flat_tube(f"ear_{sx}/inner", (sx * 0.113, 0.7, 0.014), (sx * 0.163, 0.785, 0.012),
                                        0.038, 0.02, a.inner, deep=0.3))
        elif a.ears == "small":  # little round ears high on the head
            hput(f"ear_{sx}/ear", (sx * 0.125, 0.728, -0.01), (0.046, 0.046, 0.026), a.fur, samples=(18, 12))
            hput(f"ear_{sx}/inner", (sx * 0.125, 0.725, 0.008), (0.028, 0.028, 0.012), a.inner, samples=(14, 10))
        elif a.ears == "tiny":  # a sea otter's: little buttons at the sides
            hput(f"ear_{sx}/ear", (sx * 0.172, 0.655, -0.01), (0.03, 0.03, 0.02), a.inner, samples=(14, 10))
        elif a.ears == "fluffy":  # a koala's: big round ears at the sides, pale inside
            hput(f"ear_{sx}/ear", (sx * 0.175, 0.665, -0.012), (0.088, 0.084, 0.036), a.fur, samples=(22, 14))
            hput(f"ear_{sx}/inner", (sx * 0.178, 0.662, 0.012), (0.056, 0.052, 0.018), a.inner, samples=(16, 10))
        elif a.ears == "pika":  # round ears, large for the head
            hput(f"ear_{sx}/ear", (sx * 0.14, 0.715, -0.01), (0.088, 0.09, 0.03), a.fur, samples=(22, 14))
            hput(f"ear_{sx}/inner", (sx * 0.14, 0.708, 0.01), (0.06, 0.062, 0.015), a.inner, samples=(18, 10))
        elif a.ears == "gills":  # an axolotl's: three feathery stalks at each side of the head
            for k, (dy, up) in enumerate(((0.3, 0.07), (0.05, 0.02), (-0.2, -0.04))):
                b0 = on(sx * 0.9, dy, -0.25)
                b1 = (b0[0] + sx * 0.1, b0[1] + up, b0[2] - 0.01)
                fig._extra.append(tube(f"gill_{sx}/stalk", head.point(b0), head.point(b1), 0.017, 0.008, a.inner,
                                       looks=looks, samples=(10, 12)))
        elif a.ears == "bumps":  # a frog's: two round bumps on top of the head, where its eyes would bulge
            hput(f"ear_{sx}/ear", (sx * 0.095, 0.745, 0.02), (0.062, 0.058, 0.056), a.fur, samples=(20, 14))
            hput(f"ear_{sx}/inner", (sx * 0.095, 0.75, 0.062), (0.034, 0.032, 0.018), a.inner, samples=(14, 10))
        elif a.ears == "none":
            pass
        elif a.ears == "horns":  # a dragon's: two short horns
            b0 = on(sx * 0.42, 0.82, -0.12)
            fig._extra.append(tube(f"horn_{sx}/horn", head.point(b0), head.point((b0[0] + sx * 0.035, b0[1] + 0.085,
                                                                                  b0[2] - 0.02)),
                                   0.022, 0.007, a.inner, looks=looks, samples=(10, 12)))
        elif a.ears == "fox":  # small triangles, set wide apart (an arctic fox's; an armadillo's)
            fig._extra.append(flat_tube(f"ear_{sx}/ear", (sx * 0.125, 0.69, -0.005), (sx * 0.16, 0.765, -0.005),
                                        0.05, 0.008, a.fur))
            fig._extra.append(flat_tube(f"ear_{sx}/inner", (sx * 0.128, 0.7, 0.012), (sx * 0.153, 0.748, 0.01),
                                        0.026, 0.006, a.inner, deep=0.3))
        elif a.ears == "huge":  # a fennec's: as tall as the head, leaning out
            fig._extra.append(flat_tube(f"ear_{sx}/ear", (sx * 0.1, 0.64, -0.01), (sx * 0.25, 0.93, -0.02), 0.085,
                                        0.014, a.fur))
            fig._extra.append(flat_tube(f"ear_{sx}/inner", (sx * 0.106, 0.665, 0.018), (sx * 0.235, 0.89, 0.008),
                                        0.052, 0.01, a.inner, deep=0.3))
        else:  # long bunny ears, standing up and leaning out a little
            # a leaf: narrow at the foot, widest two thirds up, a round tip (two tubes that join into one shape)
            foot, belly, tip = (sx * 0.068, 0.68, -0.01), (sx * 0.112, 0.835, -0.016), (sx * 0.128, 0.905, -0.02)
            fig._extra.append(flat_tube(f"ear_{sx}/ear", foot, belly, 0.03, 0.054, a.fur, deep=0.34))
            fig._extra.append(flat_tube(f"ear_{sx}/ear", belly, tip, 0.054, 0.04, a.fur, deep=0.34))
            foot, belly, tip = (sx * 0.078, 0.725, 0.004), (sx * 0.112, 0.835, -0.002), (sx * 0.124, 0.89, -0.006)
            fig._extra.append(flat_tube(f"ear_{sx}/inner", foot, belly, 0.012, 0.032, "bunny.inner", deep=0.3))
            fig._extra.append(flat_tube(f"ear_{sx}/inner", belly, tip, 0.032, 0.022, "bunny.inner", deep=0.3))

    ear[0] = head

    if a.visor:  # a robot's screen; from here the face is drawn on it, and lit: eyes, brows and mouth in `a.led`
        n, (A, B, Y0, sq) = 2.0 / (a.boxy[1] or 1.0), VISOR
        vx, vy, vz = (hr[i] * head.scale[i] for i in range(3))

        def plate(name, material, grow, out):  # a rounded rectangle lying on the front of the head
            fx_ = f"({A * grow:.4f}*v*sign(cos(u))*pow(abs(cos(u)),{sq}))"
            fy_ = f"({Y0:.4f}+{B * grow + A * (grow - 1) * 0.6:.4f}*v*sign(sin(u))*pow(abs(sin(u)),{sq}))"
            front = f"(pow(max(0,1-pow(abs({fx_}),{n:.4f})-pow(abs({fy_}),{n:.4f})),{1 / n:.4f})+{out})"
            fig._extra.append(m.Limb(x=f"{vx:.5f}*{fx_}", y=f"{vy:.5f}*{fy_}", z=f"{vz:.5f}*{front}", u=(0, 360),
                                     v=(0, 1), samples=(64, 6), closed=(True, False), radii=(vx, vy, vz * 1.02),
                                     at=head.point(hc), basis=head.basis(m.IDENTITY), name=name,
                                     material=material, casts_shadow=False, looks=looks))

        plate("bezel/bezel", a.inner, 1.11, VISOR_OUT * 0.55)   # a metal frame round the screen
        plate("visor/visor", a.visor, 1.0, VISOR_OUT)

        def on(fx, fy, out=0.0):
            z = max(0.0, 1 - abs(fx) ** n - abs(fy) ** n) ** (1 / n) + VISOR_OUT
            return (hc[0] + fx * hr[0], hc[1] + fy * hr[1], hc[2] + (z + out) * hr[2])

        lit = {"plush.eye": a.led, "m.ink": a.led, "m.mouth": a.led, "m.tongue": a.visor, "dev.white": None}
        limb0, stroke0 = limb, stroke

        power = max(0.0, min(1.0, fig.power))
        blank = power < 0.12 or bool(fig.icon)   # no face on the screen: it is dark, or shows a picture
        dim = power < 0.45                       # coming on or going off: only the eyes yet

        def limb(name, point, radii_, material, **kw):
            if blank or (dim and name in ("mouth", "tongue")):
                return
            material = lit.get(material, material)
            if material is not None:  # a lit eye has no shine (a dark notch in its place read as a squint)
                limb0(name, point, radii_, material, **kw)

        def stroke(name, points, r, material="m.ink"):
            if blank or (dim and name.split("/")[0] in ("brow", "mouth")):
                return
            stroke0(name, points, r * (1.7 if material == "m.ink" else 1.0), lit.get(material, material))

        if fig.icon and power >= 0.12:
            icon(on, stroke0, fig.icon, a.led)

        fig._stroke = stroke
        for sd in ("left", "right"):  # a dark cuff where each metal arm meets its hand
            if all(f"{sd}_{b}" in frames for b in ("upper_arm", "lower_arm", "hand")):
                w_ = tuple(fig.arm_points(frames, sd)[2])   # where the arm is drawn (stretched, clear of the head)
                rr = fig.spec.arm_r * 1.22
                fig._extra.append(fig._egg_part(f"cuff_{sd[0]}/cuff", tuple(w_), (rr, rr, rr), "robot.dark",
                                                samples=(12, 8)))
        for sx in (-1, 1):  # a rivet at each corner of the screen
            for fy in (0.36, -0.74):
                put(head, "rivet/rivet", on(sx * 0.79, fy, -VISOR_OUT), (0.011, 0.011, 0.006), a.inner,
                    samples=(10, 8))

    # eyes, brows, blush: the shared face
    if a.patch:  # a dark patch round each eye, lying on the face under the eye
        from srlocations.geometry import rotation as _rot
        for sx in (-1, 1):
            put(head, "patch/patch", on(sx * (EYE_X + 0.01), EYE_Y - 0.03, -0.045), (0.05, 0.062, 0.011), a.patch,
                _rot(0, 0, sx * 18), (16, 10))
    seen = e if not (fig.look_x or fig.look_y) else _replace(e, look=(e.look[0] + fig.look_x, e.look[1] + fig.look_y))
    eyes(on, limb, stroke, R, seen, a.eyes, a.visor or a.patch or a.head or a.fur,
         shut=max(fig.lid, 1.0 - fig.power) if a.visor else fig.lid, scale=fig.eye_scale,
         shut_each=(fig.lid_left, fig.lid_right), screen=bool(a.visor))
    fig._rest_mouth = a.rest_mouth
    m.brows(on, stroke, e, EYE_X, 0.12, 0.11, 0.0065, was=fig.brows_from, mix=fig.brow_mix,
            lift=0.3 * (fig.eye_scale - 1.0))
    for sx in (-1, 1):
        if not a.visor:  # a robot does not blush
            put(head, "cheek/blush", on(sx * 0.66, -0.5, -0.04),
                (0.045 * fig.blush, 0.028 * fig.blush, 0.022), "plush.blush", samples=(14, 10))
        if a.marks == "panda":  # a red panda's white spots over the eyes (its wide white muzzle is the MUZZLES entry)
            put(head, "mark/brow", on(sx * EYE_X, 0.2, -0.05), (0.034, 0.02, 0.02), a.light, samples=(14, 10))
            put(head, "mark/cheek", on(sx * 0.74, -0.42, -0.1), (0.07, 0.062, 0.03), a.light, samples=(16, 10))
    mouth = a.rest_mouth if (e.mouth == "flat" and a.rest_mouth) else e.mouth

    # muzzle, nose and mouth
    if a.muzzle in MUZZLES:
        (fy, out), (sx_, sy_, sz_), nose_r, nose_fy = MUZZLES[a.muzzle]
        # small and low, between and under the eyes (the entries were drawn for a higher, larger muzzle)
        mc = on(0.0, fy - 0.14, out)
        mr = (0.7 * sx_ * R.x, 0.8 * sy_ * R.y, 0.85 * sz_ * R.z)
        put(head, "muzzle/muzzle", mc, mr, a.light, samples=(20, 14))
        mon = _ellipsoid_on(mc, mr)
        if a.muzzle in ("hippo", "dragon"):  # two nostrils high on the big muzzle, no nose
            for sx in (-1, 1):
                put(head, "nose/nostril", mon(sx * 0.32, nose_fy, 0.0), nose_r, a.nose, samples=(10, 8))
        else:
            put(head, "nose/nose", mon(0.0, nose_fy, 0.02), nose_r, a.nose or "bear.nose", samples=(14, 10))
        if mouth not in ("open", "yell", "o") and a.muzzle not in ("hippo", "dragon"):
            pass  # no line from nose to mouth: on a small muzzle it only added dark strokes
        # the muzzle is short: open mouths are measured on a taller scale, so they open; lines keep their weight
        fig._lip(mon, limb, Vec3(mr[0], mr[1] * 2.5, mr[2]), mouth, -0.15, 0.62, line=0.044)
    elif a.muzzle == "pig":
        sc = on(0.0, -0.52, 0.02)
        put(head, "snout/snout", sc, (0.07, 0.05, 0.04), "pig.snout", samples=(20, 12))
        for sx in (-1, 1):
            put(head, "snout/nostril", (sc[0] + sx * 0.022, sc[1], sc[2] + 0.036), (0.009, 0.015, 0.006),
                "pig.nostril", samples=(10, 8))
        fig._lip(on, limb, R, mouth, -0.8, 0.15, line=0.028)
    elif a.muzzle == "robot":  # no nose: a short mouth on the face plate
        fig._lip(on, limb, R, mouth, -0.5, 0.2, line=0.028)
    elif a.muzzle in ("axolotl", "shark"):  # no nose: a wide mouth across the face
        fig._lip(on, limb, R, mouth, -0.52, 0.3, line=0.028)
        if a.muzzle == "shark" and mouth not in ("open", "yell", "o"):  # a row of little teeth under the line
            curve = {"smile": 0.09, "smug": 0.05, "frown": -0.07}.get(mouth, 0.0)
            for i in range(-2, 3):
                u = i * 0.1 / 0.3
                put(head, "teeth/tooth", on(i * 0.1, -0.52 + curve * u * u - 0.05, 0.005), (0.011, 0.014, 0.006),
                    "m.white", samples=(8, 6))
    elif a.muzzle in ("beak", "bill"):  # a bird: two halves that part when it speaks
        gap = {"open": 0.05, "yell": 0.09, "o": 0.035, "wavy": 0.02}.get(mouth, 0.0) * R.y
        bx, by, bz = on(0.0, -0.48, 0.0)
        if gap:
            put(head, "beak-in/inside", (bx, by - 0.012 - gap * 0.5, bz + 0.0), (0.045, gap * 0.6 + 0.004, 0.03),
                "m.mouth", samples=(12, 8))
        if a.muzzle == "beak":  # an eagle's: deep, with a hooked tip
            put(head, "beak/upper", (bx, by + 0.012, bz + 0.02), (0.046, 0.036, 0.062), a.nose, samples=(16, 10))
            put(head, "beak/hook", (bx, by - 0.016, bz + 0.068), (0.016, 0.028, 0.018), a.nose, samples=(12, 8))
            put(head, "beak/lower", (bx, by - 0.024 - gap, bz + 0.006), (0.032, 0.015, 0.036), a.nose, samples=(14, 8))
        else:  # a duck's: wide and flat
            put(head, "beak/upper", (bx, by + 0.01, bz + 0.03), (0.082, 0.024, 0.072), a.nose, samples=(18, 10))
            put(head, "beak/lower", (bx, by - 0.02 - gap, bz + 0.02), (0.066, 0.016, 0.056), a.nose, samples=(16, 8))
    elif a.muzzle == "grin":  # a quokka: a dark nose and its wide smile straight on the face
        put(head, "nose/nose", on(0.0, -0.38, 0.02), (0.03, 0.021, 0.02), a.nose, samples=(14, 10))
        fig._lip(on, limb, R, mouth, -0.56, 0.26, line=0.028)
    elif a.muzzle == "koala":  # a big dark oval nose down the middle of the face, the mouth under it
        put(head, "nose/nose", on(0.0, -0.4, -0.01), (0.042, 0.056, 0.035), a.nose, samples=(18, 12))
        fig._lip(on, limb, R, mouth, -0.78, 0.13, line=0.028)
    else:  # kitten, bunny, pika: a small pink nose, the mouth under it
        nose = a.nose or ("cat.nose" if a.muzzle == "cat" else "bunny.nose")
        put(head, "nose/nose", on(0.0, -0.4, 0.02), (0.022, 0.016, 0.015), nose, samples=(12, 8))
        if mouth not in ("open", "yell", "o"):
            stroke("mouth/line", [on(0.0, -0.43, 0.01), on(0.0, -0.52, 0.01)], 0.0022)
        fig._lip(on, limb, R, mouth, -0.55, 0.15, line=0.026)

    if a.stripes:
        for dx in (-0.14, 0.0, 0.14):  # forehead stripes
            stroke("stripe/line", [on(dx, 0.88, 0.0), on(dx * 1.05, 0.66, 0.01)], 0.006, a.stripes)
    if a.cheeks:
        for sx in (-1, 1):
            for fy in (0.08, -0.1, -0.28):
                stroke("stripe/cheek", [on(sx * 0.96, fy, 0.0), on(sx * 0.78, fy - 0.03, 0.01)], 0.0055, a.cheeks)
    if a.whiskers:
        for sx in (-1, 1):
            # Stitched whiskers on the muzzle, as a plush cat has them: two each side, from beside the nose and the
            # mouth, fanning out a little, and short enough to end before the blush (which starts at fx ~0.47 and
            # grows with a giggle). Lower on the face they read as a chin or a neck (operator, 2026-11-11: "quase
            # no pescoço"); across the blush they merge with it. Both ends lie on the face, so the stitch follows it.
            for fy0, fy1 in ((WHISKER_Y[0], WHISKER_Y[0] + 0.035), (WHISKER_Y[1], WHISKER_Y[1] - 0.035)):
                p0 = on(sx * WHISKER_X[0], fy0, 0.012)
                p1 = on(sx * WHISKER_X[1], fy1, 0.018)
                fig._extra.append(tube("whisker/w", head.point(tuple(p0)), head.point(tuple(p1)), 0.002, 0.0015,
                                       "plush.stitch", looks=looks, samples=(6, 9)))
    if e.mouth in ("open", "yell") and a.muzzle == "bunny":
        put(head, "teeth/teeth", on(0.0, -0.52, 0.04), (0.018, 0.014, 0.008), "m.white", samples=(10, 8))

    # belly and tail
    if not a.visor:  # (a robot has a chest panel instead: see accessory())
        bput("belly/belly", (0.0, 0.255, 0.085), (0.125, 0.1, 0.07), a.belly or a.light)  # a wide simple oval

    # Seated, a long tail rests on the seat, curled round beside the body with its tip in front (fig.tail_side:
    # +1 = the figure's local +x side), so it shows from the front instead of hiding behind the body.
    curled = "sit" in e.extras and a.tail in ("long", "ringed", "brush", "thin", "thick")
    side = 1.0 if fig.tail_side >= 0 else -1.0

    def curl(r, reach=1.0):
        """The seated tail's path for a tail of radius r: out from the root, round the hip, forward to the tip."""
        y, x = 0.118 + r, 0.165 + r + 0.012
        path = [(0.0, 0.17, -0.11), (0.09, y + 0.01, -0.165), (x - 0.02, y, -0.11), (x + 0.01, y, -0.01),
                (x + 0.005, y, 0.02 + 0.09 * reach), (x - 0.025, y + 0.012, 0.03 + 0.16 * reach)]
        return [(side * q[0], q[1], q[2]) for q in path]

    class Tail:
        """The body's carry with the tail swung about its root (fig.tail_sway to the figure's right, fig.tail_lift
        up, degrees), bending along its length: the tip takes more of the angle than the root. A curled (seated)
        tail keeps its root still and moves its front half: the tip flicks out and lifts."""
        pivot = bd((side * 0.2, 0.14, -0.05)) if curled else bd((0.0, 0.18, -0.11))
        scale, basis, vec = body.scale, body.basis, body.vec

        @staticmethod
        def point(p):
            dx, dy, dz = (p[k] - Tail.pivot[k] for k in range(3))
            if curled:
                g = max(0.0, min(1.5, (dz + 0.01) / (0.11 * KB)))   # only what lies in front of the hip moves
                a = math.radians(fig.tail_sway) * g * side
                a = -abs(a) if a > 0 else a * 0.9                   # the tip flicks outward, never into the leg
                a, b = a * side, -math.radians(abs(fig.tail_lift) + 0.6 * abs(fig.tail_sway)) * g * 0.7
            else:
                g = min(1.8, math.sqrt(dx * dx + dy * dy + dz * dz) / 0.14)
                a, b = math.radians(fig.tail_sway) * g, math.radians(fig.tail_lift) * g
            x, z = dx * math.cos(a) - dz * math.sin(a), dz * math.cos(a) + dx * math.sin(a)   # sway: about the upright
            y, z = dy * math.cos(b) - z * math.sin(b), z * math.cos(b) + dy * math.sin(b)     # lift: the tip rises
            return body.point((Tail.pivot[0] + x, Tail.pivot[1] + y, Tail.pivot[2] + z))

    def tput(name, p, r, material, samples=(20, 14)):
        put(Tail, name, bd(p), tuple(x * KB for x in r), material, m.IDENTITY, samples)

    if a.tail == "ball":
        tput("tail/tail", (0.0, 0.2, -0.13), (0.035, 0.035, 0.035), a.fur, samples=(14, 10))
    elif a.tail == "puff":
        tput("tail/tail", (0.0, 0.2, -0.13), (0.05, 0.05, 0.05), "bunny.light", samples=(16, 12))
    elif a.tail == "long":
        pts = m.smooth(curl(0.018) if curled else [(0.0, 0.18, -0.11), (0.06, 0.14, -0.2), (0.14, 0.18, -0.24),
                                                    (0.18, 0.3, -0.22), (0.16, 0.4, -0.18)], 5)
        pts = [bd(q) for q in pts]
        for p0, p1 in zip(pts, pts[1:]):
            fig._extra.append(tube("tail/seg", Tail.point(p0), Tail.point(p1), 0.018, 0.018, a.fur, looks=looks,
                                   samples=(10, 12)))
        if a.tail2:  # a tuft at the end (a lion's)
            put(Tail, "tail/tuft", pts[-1], (0.036, 0.04, 0.036), a.tail2, m.IDENTITY, (14, 10))
    elif a.tail in ("ringed", "brush"):  # a big bushy tail curving up behind: ringed, or with a dark tip
        if curled:
            pts = [bd(q) for q in m.smooth(curl(a.tail_k * 0.04), 5)]
        else:
            pts = m.smooth([(0.0, 0.16, -0.11), (0.05, 0.1, -0.2), (0.13, 0.12, -0.27), (0.2, 0.24, -0.27),
                            (0.21, 0.4, -0.22)], 5)
            pts = [bd((q[0] * (1 + 0.7 * (a.tail_k - 1)), q[1], q[2])) for q in pts]
        n = len(pts) - 1
        for i, (p0, p1) in enumerate(zip(pts, pts[1:])):
            t = i / n
            r = a.tail_k * (0.022 + 0.02 * math.sin(math.pi * min(1.0, t * 1.15)))
            if a.tail == "ringed":
                mat = a.tail2 if (i // 3) % 2 else a.fur
            else:
                mat = a.tail2 if t > 0.78 else a.fur
            fig._extra.append(tube("tail/seg", Tail.point(p0), Tail.point(p1), r, r, mat, looks=looks,
                                   samples=(12, 12)))
    elif a.tail == "none":
        pass
    elif a.tail in ("thin", "thick"):  # a short tapering tail resting on the ground behind (an otter's is thick)
        k = 1.9 if a.tail == "thick" else 1.0
        pts = [bd(q) for q in (m.smooth(curl(k * 0.017, 0.75), 5) if curled else
                               m.smooth([(0.0, 0.17, -0.12), (0.02, 0.1, -0.2), (0.03, 0.05, -0.29)], 4))]
        n = len(pts) - 1
        for i, (p0, p1) in enumerate(zip(pts, pts[1:])):
            r0, r1 = k * (0.017 - 0.011 * i / n), k * (0.017 - 0.011 * (i + 1) / n)
            fig._extra.append(tube("tail/seg", Tail.point(p0), Tail.point(p1), r0, r1, a.tail2 or a.fur,
                                   looks=looks, samples=(10, 12)))
    else:  # a curly piggy tail
        pts = [(0.025 * (1 - i / 22) * math.cos(i * 0.62), 0.22 + 0.025 * (1 - i / 22) * math.sin(i * 0.62),
                -0.13 - i * 0.004) for i in range(14)]
        pts = [bd(q) for q in pts]
        for p0, p1 in zip(pts, pts[1:]):
            fig._extra.append(tube("tail/seg", Tail.point(p0), Tail.point(p1), 0.007, 0.007, a.fur, looks=looks,
                                   samples=(8, 9)))
    # a stitched seam down the middle of the tummy
    bc, br = bd((0.0, 0.27, 0.075)), tuple(x * KB for x in (0.11, 0.12, 0.075))
    bon = _ellipsoid_on(bc, br)
    for i in range(0):  # the seam is off: it competed with the face (the operator's review, 2026-11-11)
        t0 = 0.78 - i * 0.24
        fig._extra.append(tube("stitch/dash", body.point(bon(0.0, t0, 0.03)), body.point(bon(0.0, t0 - 0.12, 0.03)),
                               0.0017, 0.0017, "plush.stitch", looks=looks, samples=(6, 8)))
    own_parts(fig, a, body, head, put)
    accessory(fig, a, body, head, put, on)
    if "sweat" in e.extras:
        hput("sweat/drop", (-0.21, 0.72, 0.1), (0.016, 0.026, 0.016), "m.sweat", samples=(10, 8))
    return fig._take_extra()


def own_parts(fig, a: Animal, body, head, put) -> None:
    """What only some animals have (`Animal.extras`), on the rest-pose head (HEAD) and body (BODY)."""
    looks = fig.looks
    (hx, hy, hz), (rx, ry, rz) = HEAD
    if "mane" in a.extras:  # a ring of tufts round the face, behind it
        for k in range(12):
            t = math.radians(30 * k + 15)
            put(head, "mane/tuft", (hx + math.cos(t) * rx * 0.97, hy + math.sin(t) * ry * 0.97, hz - 0.035),
                (0.078, 0.078, 0.06), "lion.mane", m.IDENTITY, (16, 10))
    if "spikes" in a.extras:  # three spikes from the top of the head down the back of it
        for deg in (5, 38, 70):
            t = math.radians(deg)
            n = (0.0, math.cos(t), -math.sin(t))
            b0 = (hx, hy + n[1] * ry * 0.95, hz + n[2] * rz * 0.95)
            fig._extra.append(tube("spike/spike", head.point(b0), head.point((b0[0], b0[1] + n[1] * 0.06,
                                                                               b0[2] + n[2] * 0.06)),
                                   0.024, 0.006, "dragon.wing", looks=looks, samples=(10, 12)))
    if "wings" in a.extras:  # two small wings on the back
        for sx in (-1, 1):
            fig._extra.append(tube(f"wing_{sx}/wing", body.point((sx * 0.07, 0.19, -0.1)),
                                   body.point((sx * 0.26, 0.33, -0.16)), 0.06, 0.012, "dragon.wing",
                                   ref=body.vec((0, 1, 0)), wide=1.0, deep=0.22, looks=looks, samples=(14, 18)))
    if "shell" in a.extras:  # a three-banded armadillo's armour: a shell over the back, a plate on the head
        (bx, by, bz), (brx, bry, brz) = fig.spec.body[:2]
        sx_, sy_, sz_ = brx * 1.2, bry * 1.1, brz * 1.0  # wider than the body: it wraps the sides, seen from the front
        put(body, "shell/shell", (bx, by + 0.012, bz - 0.035), (sx_, sy_, sz_), "armadillo.shell", m.IDENTITY, (28, 18))
        for dy in (-0.045, 0.0, 0.045):  # the three bands, round the back and the sides to the front edge
            k = math.sqrt(max(0.05, 1 - (dy / sy_) ** 2)) * 1.01
            pts = [(bx + sx_ * k * math.sin(math.radians(d)), by + 0.012 + dy, bz - 0.035 - sz_ * k * math.cos(math.radians(d)))
                   for d in range(-150, 151, 15)]
            for p0, p1 in zip(pts, pts[1:]):
                fig._extra.append(tube("band/seg", body.point(p0), body.point(p1), 0.004, 0.004, "armadillo.band",
                                       looks=looks, samples=(6, 8)))
        put(head, "plate/plate", (hx, hy + 0.34 * ry, hz - 0.06 * rz), (0.8 * rx, 0.76 * ry, 0.9 * rz),
            "armadillo.shell", m.IDENTITY, (24, 14))
    if "dorsal" in a.extras:  # a shark's fin on top of the head, swept back
        fig._extra.append(tube("fin/dorsal", head.point((hx, hy + 0.88 * ry, hz - 0.2 * rz)),
                               head.point((hx, hy + 1.5 * ry, hz - 0.75 * rz)), 0.07, 0.014, a.fur,
                               ref=head.vec((0, 0, 1)), wide=1.0, deep=0.22, looks=looks, samples=(14, 18)))


def accessory(fig, a: Animal, body, head, put, on) -> None:
    """Each animal's one accessory (on the rest-pose skeleton: the neck is at y 0.31, its front at z 0.06)."""
    from srlocations.geometry import rotation
    looks = fig.looks

    def ring(material):  # a ring round the neck
        fig._extra.append(m.Limb(x="(0.068+0.009*cos(v))*cos(u)", y="0.009*sin(v)", z="(0.06+0.009*cos(v))*sin(u)",
                                 u=(0, 360), v=(0, 360), samples=(36, 8), closed=(True, True),
                                 radii=(0.077, 0.009, 0.069), at=body.point((0.0, 0.268, 0.045)),
                                 basis=body.basis(m.IDENTITY), name="collar/ring", material=material,
                                 casts_shadow=False, looks=looks))

    if "ring" in a.extras:  # a robot's neck joint
        ring(a.inner)
    if "handle" in a.extras:  # a mug's handle on one side of the head
        (hx, hy, hz), (hrx, _hry, _hrz) = HEAD
        big, thin = 0.05, 0.014
        fig._extra.append(m.Limb(x=f"({big}+{thin}*cos(v))*cos(u)", y=f"({big}+{thin}*cos(v))*sin(u)",
                                 z=f"-{thin}*sin(v)", u=(0, 360), v=(0, 360), samples=(28, 8), closed=(True, True),
                                 radii=(big + thin, big + thin, thin), at=head.point((hx - hrx - 0.012, hy, hz)),
                                 basis=head.basis(m.IDENTITY), name="handle/handle", material=a.tail2,
                                 casts_shadow=False, looks=looks))
    if a.extra in ("core", "buttons", "gauge", "bars", "bean", "letterc", "indent", "lines", "dots"):  # a robot's chest: drawn on the front of its square body
        (bx, by, bz), (brx, bry, brz) = fig.spec.body[:2]
        n = 2.0 / (a.boxy[0] or 1.0)
        across = body.vec((1, 0, 0))

        def at(dx, dy, lift=0.0):  # metres from the middle of the chest, and out of it
            z = max(0.0, 1 - abs(dx / brx) ** n - abs(dy / bry) ** n) ** (1 / n)
            return (bx + dx, by + dy, bz + brz * z + lift)

        if a.extra == "core":  # a round light in a dark ring
            put(body, "core/ring", at(0.0, 0.005), (0.05, 0.05, 0.01), "robot.dark", m.IDENTITY, (22, 10))
            put(body, "corelight/light", at(0.0, 0.005, 0.006), (0.034, 0.034, 0.008), a.led, m.IDENTITY, (18, 10))
        elif a.extra == "buttons":  # three buttons and a slot under them
            for i, mat in enumerate(("robot.red", "robot.green", "robot.blue")):
                put(body, f"button_{i}/button", at((i - 1) * 0.05, 0.02), (0.019, 0.019, 0.011), mat,
                    m.IDENTITY, (14, 10))
            fig._extra.append(tube("slot/slot", body.point(at(-0.045, -0.04, 0.002)), body.point(at(0.045, -0.04, 0.002)),
                                   0.0045, 0.0045, "robot.dark", looks=looks, samples=(8, 9)))
        elif a.extra == "gauge":  # a dial with a needle
            put(body, "gauge/dial", at(0.0, 0.0), (0.052, 0.052, 0.012), "m.white", m.IDENTITY, (22, 10))
            fig._extra.append(tube("needle/needle", body.point(at(0.0, -0.014, 0.013)), body.point(at(-0.022, 0.028, 0.011)),
                                   0.0045, 0.003, "robot.red", looks=looks, samples=(8, 9)))
            put(body, "needle/hub", at(0.0, -0.014, 0.013), (0.009, 0.009, 0.007), "robot.dark", m.IDENTITY, (10, 8))
        elif a.extra in ("lines", "dots"):  # a speech bubble (picture left is +x): text in it, or three dots
            k = 1.0 if a.extra == "lines" else -1.0  # which side its tail is on
            put(body, "bubble/bubble", at(0.0, 0.008), (0.064, 0.044, 0.01), a.tail2, m.IDENTITY, (24, 12))
            fig._extra.append(tube("bubble/tail", body.point(at(k * 0.026, -0.022, 0.0)), body.point(at(k * 0.05, -0.056, 0.0)),
                                   0.014, 0.003, a.tail2, ref=across, deep=0.4, looks=looks, samples=(10, 12)))
            if a.extra == "lines":
                for x0, x1, y in ((-0.036, 0.036, 0.02), (-0.036, 0.014, -0.002)):
                    fig._extra.append(tube("text/line", body.point(at(-x0, y, 0.011)), body.point(at(-x1, y, 0.011)),
                                           0.0058, 0.0058, a.fur, looks=looks, samples=(8, 9)))
            else:
                for x in (-0.027, 0.0, 0.027):
                    put(body, "text/dot", at(x, 0.008, 0.011), (0.0085, 0.0085, 0.006), a.fur, m.IDENTITY, (10, 8))
        elif a.extra == "bean":  # a coffee bean
            put(body, "bean/bean", at(0.0, 0.0), (0.034, 0.047, 0.012), "java.bean", rotation(0, 0, 18), (18, 12))
            pts = [at(0.016 * math.sin(math.radians(k * 45 - 90)) * 0.5 + 0.0105 * (k - 4) / 4, 0.036 * (k - 4) / 4, 0.011)
                   for k in range(9)]
            for p0, p1 in zip(pts, pts[1:]):
                fig._extra.append(tube("beancrease/crease", body.point(p0), body.point(p1), 0.0035, 0.0035,
                                       "java.crease", looks=looks, samples=(6, 8)))
        elif a.extra == "letterc":  # the letter C (a camera on +z sees +x on its left, so the gap is at -x)
            pts = [at(-0.04 * math.cos(math.radians(d)), 0.044 * math.sin(math.radians(d)), 0.004)
                   for d in range(50, 311, 20)]
            for p0, p1 in zip(pts, pts[1:]):
                fig._extra.append(tube("letter/c", body.point(p0), body.point(p1), 0.011, 0.011, a.tail2,
                                       looks=looks, samples=(10, 10)))
        elif a.extra == "indent":  # lines of code, indented (picture left is +x)
            for x0, x1, y in ((-0.05, 0.03, 0.036), (-0.022, 0.05, 0.012), (-0.022, 0.034, -0.012), (-0.05, 0.008, -0.036)):
                fig._extra.append(tube("code/line", body.point(at(-x0, y, 0.003)), body.point(at(-x1, y, 0.003)),
                                       0.0065, 0.0065, a.nose, looks=looks, samples=(8, 9)))
        else:  # a battery's three bars, rising to the picture's right (a camera on +z sees +x on its left)
            for i, x in enumerate((0.05, 0.0, -0.05)):
                fig._extra.append(tube(f"bar_{i}/bar", body.point(at(x, -0.035, 0.003)),
                                       body.point(at(x, -0.015 + 0.027 * i, 0.003)), 0.014, 0.014, "robot.green",
                                       ref=across, looks=looks, samples=(10, 12)))
    if a.extra == "bowtie":  # a bow tie under the chin
        for sx in (-1, 1):
            put(body, "bowtie/loop", (sx * 0.03, 0.262, 0.112), (0.03, 0.021, 0.014), "bear.bow",
                rotation(0, 0, sx * 12), (16, 10))
        put(body, "bowtie/knot", (0.0, 0.262, 0.122), (0.013, 0.015, 0.012), "bear.bow", m.IDENTITY, (12, 8))
    elif a.extra == "collar":  # a collar round the neck with a bell
        fig._extra.append(m.Limb(x="(0.068+0.009*cos(v))*cos(u)", y="0.009*sin(v)", z="(0.06+0.009*cos(v))*sin(u)",
                                 u=(0, 360), v=(0, 360), samples=(36, 8), closed=(True, True),
                                 radii=(0.077, 0.009, 0.069), at=body.point((0.0, 0.268, 0.045)),
                                 basis=body.basis(m.IDENTITY), name="collar/ring", material="cat.collar",
                                 casts_shadow=False, looks=looks))
        put(body, "bell/bell", (0.0, 0.25, 0.118), (0.019, 0.019, 0.019), "cat.bell", m.IDENTITY, (14, 10))
    elif a.extra == "flower":  # a little flower on the head, by the ear
        cx, cy, cz = on(-0.36, 0.72, 0.0)
        for k in range(5):
            t = math.radians(90 + 72 * k)
            put(head, "flower/petal", (cx + 0.021 * math.cos(t), cy + 0.021 * math.sin(t), cz + 0.004),
                (0.015, 0.015, 0.007), "pig.petal", m.IDENTITY, (12, 8))
        put(head, "flower/heart", (cx, cy, cz + 0.009), (0.011, 0.011, 0.009), "pig.heart", m.IDENTITY, (10, 8))
    elif a.extra == "clam":  # a sea otter holds a shell on its tummy
        (bx, by, bz), (brx, bry, brz) = fig.spec.body[:2]
        put(body, "clam/shell", (bx, by + 0.02, bz + brz * 1.0), (0.05, 0.04, 0.02), "otter.shell", m.IDENTITY, (16, 10))
        for dx in (-0.022, 0.0, 0.022):
            fig._extra.append(tube("clam/rib", body.point((bx + dx * 0.4, by - 0.012, bz + brz + 0.02)),
                                   body.point((bx + dx, by + 0.05, bz + brz + 0.016)), 0.002, 0.002, "plush.stitch",
                                   looks=looks, samples=(6, 8)))
    elif a.extra == "sprig":  # a pika carries a sprig of flowers in its mouth
        x0, y0, z0 = on(0.02, -0.56, 0.03)
        tip = (x0 - 0.13, y0 + 0.035, z0 - 0.02)
        fig._extra.append(tube("sprig/stem", head.point((x0, y0, z0)), head.point(tip), 0.005, 0.004, "pika.stem",
                               looks=looks, samples=(8, 10)))
        for dx, dy in ((0.0, 0.0), (0.035, 0.02), (0.02, -0.022)):
            put(head, "sprig/bloom", (tip[0] + dx, tip[1] + dy, tip[2] + 0.006), (0.017, 0.017, 0.012), "pika.bloom",
                m.IDENTITY, (12, 8))
    elif a.extra == "bow":  # a bow at the foot of the right ear
        bx, by, bz = on(0.3, 0.8, 0.0)  # on the head's surface, in front of the ear's foot
        for sx in (-1, 1):
            put(head, "bow/loop", (bx + sx * 0.028, by, bz + 0.03), (0.027, 0.018, 0.012), "bunny.bow",
                rotation(0, 0, sx * 14), (16, 10))
        put(head, "bow/knot", (bx, by, bz + 0.038), (0.011, 0.012, 0.01), "bunny.bow", m.IDENTITY, (10, 8))


for _k in ANIMALS:
    m.BUILDERS[_k] = build
    m.LOOKS[_k] = look


def lineup(out: Optional[Path] = None, who: Optional[list[str]] = None) -> Path:
    """The family (or `who` of it) side by side in three views (front, three-quarter, profile)."""
    who = who or list(ANIMALS)
    out = out or ROOT / "sheets" / "3d" / ("plush-lineup.png" if len(who) == len(ANIMALS) else
                                           f"plush-lineup-{'-'.join(who)}.png")
    rows = []
    for label, yaw in (("front", 0), ("three-quarter", 330), ("profile", 270)):
        loc = m._stage("plush-lineup")
        for i, k in enumerate(who):
            loc.add(m.figure(k, "idle", name=k, at=((i - (len(who) - 1) / 2) * 0.62, 0, 0), yaw=yaw))
        far = 12.5 * max(1.0, len(who) / 4)
        loc.shot("row", (0.0, 0.45, far), (0.0, 0.45, 0), lens=150)
        tile = out.parent / f".plush-lineup-{label}.png"
        render(loc, "row", tile, 1600, 640, look())
        rows.append(tile)
    subprocess.run(["ffmpeg", "-v", "error", "-y", *[a for t in rows for a in ("-i", str(t))], "-filter_complex",
                    f"vstack={len(rows)}", str(out)], check=True)
    for t in rows:
        t.unlink()
    return out


def alive(who: Optional[list[str]] = None, seconds: float = 6.0, fps: int = 12, out: Optional[Path] = None) -> Path:
    """A test of life: the animals breathe, blink and tilt their heads, each in its own time. The face cannot be
    keyed over time on the skeleton, so every frame is a still of figures built for that instant (drawn on twos:
    `fps` stills a second, played at twice that)."""
    from dataclasses import replace
    who = who or ["cat", "bunny", "axolotl", "pig", "koala"]
    out = (out or ROOT / "examples" / "out" / "plush-alive.mp4").resolve()
    work = out.parent / ".plush-alive"
    work.mkdir(parents=True, exist_ok=True)
    rest = {k: m.SPECS[k] for k in who}
    frames = int(seconds * fps)
    try:
        for f in range(frames):
            t = f / fps
            loc = m._stage("plush-alive")
            for i, k in enumerate(who):
                spec, phase = rest[k], i * 1.7
                breath = math.sin(2 * math.pi * t / 3.2 + phase)
                (bc, br, bm), (hc, hr, hm) = spec.body, spec.head
                body = ((bc[0], bc[1] + 0.012 * br[1] * breath, bc[2]),
                        (br[0] * (1 + 0.012 * breath), br[1] * (1 + 0.03 * breath), br[2] * (1 + 0.02 * breath)), bm)
                head = ((hc[0], hc[1] + 0.005 * breath, hc[2]), hr, hm)  # the head rides on the breath
                m.SPECS[k] = replace(spec, body=body, head=head)
                blink = (t + phase * 0.9) % 2.9 < 2 / fps  # shut for two stills, about every three seconds
                tilt = spec.stance.get("head.tilt_left_right", 0.0) + 5.0 * math.sin(2 * math.pi * t / 4.5 + phase)
                pose = replace(m.POSES[k]["idle"], eyes="closed" if blink else "normal",
                               joints=(("head.tilt_left_right", max(-20.0, min(20.0, tilt))),))
                loc.add(m.figure(k, pose, name=k, at=((i - (len(who) - 1) / 2) * 0.62, 0, 0)))
            loc.shot("row", (0.0, 0.38, 12.5 * max(1.0, len(who) / 4)), (0.0, 0.38, 0), lens=150)
            render(loc, "row", work / f"f{f:04d}.png", 1600, 640, look())
    finally:
        m.SPECS.update(rest)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", str(work / "f%04d.png"), "-r",
                    str(fps * 2), "-pix_fmt", "yuv420p", "-crf", "16", str(out)], check=True)
    for png in work.glob("f*.png"):
        png.unlink()
    work.rmdir()
    return out


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "lineup"
    if what == "sheet":
        for who in sys.argv[2:] or list(ANIMALS):
            print("wrote", m.sheet(who))
    elif what == "lineup":
        print("wrote", lineup(who=sys.argv[2:] or None))
    elif what == "alive":
        print("wrote", alive(sys.argv[2:] or None))
    elif what == "view":
        print("wrote", m.view(sys.argv[2], sys.argv[3], float(sys.argv[4]), Path(sys.argv[5])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
