"""The page the characters are drawn on: a scene on paper, and the light of a photo of that paper over it.

The marker style gives every volume an opaque underfill of PAPER, so the scene background must be PAPER too, and
the photo's light, fibres, lens softness and grain must go over everything drawn (photograph(), before captions).
The light was measured on the reference Reel's frames: top #F4F4EF, bottom #B4B3A9.
"""

from __future__ import annotations

from pathlib import Path

from . import marker

W, H, FPS = 1080, 1920, 24
LIGHT_STOPS = [(0.0, "#FFFFFFFF"), (0.18, "#F3F3EEFF"), (0.38, "#E1E1D9FF"), (0.56, "#D7D7CFFF"),
               (0.76, "#D1D1C9FF"), (0.9, "#C9C9C1FF"), (1.0, "#B9B9B1FF")]


def new_scene(duration: float, scene_dir: str | Path, width: int = W, height: int = H, fps: int = FPS,
              background: str = marker.PAPER):
    """A scene on paper with the drawing effects declared. `scene_dir` is where its XML will be written (the
    pencil shader is referenced relative to it). Returns (scene, assets, composition, character effects).
    Pass background="#00000000" for transparent cut-outs."""
    from sr_core.scene import Scene

    scene = Scene(version="auto")
    scene.add_project(width=width, height=height, fps=str(fps), duration=round(duration, 3), background=background)
    assets = scene.add_assets()
    paints = scene.add_paints()
    g = paints.add_linearGradient(id="photo-light", units="object", x1=0, y1=0, x2=0, y2=1)
    for off, col in LIGHT_STOPS:
        g.add_stop(offset=off, color=col)
    r = paints.add_radialGradient(id="photo-falloff", units="object")
    r.add_stop(offset=0.0, color="#FFFFFFFF")
    r.add_stop(offset=0.45, color="#FFFFFFFF")
    r.add_stop(offset=1.0, color="#F4F4F0FF")
    fx = scene.add_effects()
    effects = marker.add_effects(fx, scene_dir)
    fx.add_effect(id="cam-soft", type="blur", radius=0.7)
    fx.add_effect(id="cam-grain", type="film-grain", amount=0.035, size=1.6, seed=5)
    comp = scene.add_composition()
    return scene, assets, comp, effects


def photograph(assets, comp, width: int = W, height: int = H, camera_id: str = "camera") -> None:
    """Everything drawn so far becomes a photo of paper: light, fibres, a soft lens and sensor grain.
    Call it after the characters and before the captions (captions stay crisp, as in the reference)."""
    comp.add_shape(id="photo-light-rect", shape="rect", x=0, y=0, width=width, height=height,
                   fill="url(#photo-light)", blend="multiply")
    comp.add_shape(id="photo-falloff-rect", shape="rect", x=0, y=0, width=width, height=height,
                   fill="url(#photo-falloff)", blend="multiply")
    fibres = assets.add_generator(id="fibres", kind="fractal-noise", width=width, height=height, scale=2, octaves=5,
                                  paint="#FFFFFFFF", paint2="#C9C4B6FF", seed=7)
    comp.add_layer(id="paper-fibres", asset=fibres, opacity=0.3, blend="multiply")
    comp.add_adjustment(id=camera_id, effects="cam-soft cam-grain")
