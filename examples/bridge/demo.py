"""The bridge's demonstration, with no srstudio: a cutout from a request (the command line), the airliner drawn
through the same shot by our engine, the two laid together by a scene written by hand, and the numbers.

    SRLOCATIONS_PY characters/examples/bridge/demo.py     (from the folder that holds characters/; about 15 minutes of GPU)

What it makes goes to examples/out/bridge/airliner, which git ignores.
"""
import json
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))          # the folder that holds characters/

from sr_core.scene import Scene  # noqa: E402
from srlocations import Registry, Renderer, SharedCatalog, Shaded  # noqa: E402

from characters import blender, bridge, clip, clip_record, export  # noqa: E402

PIL_PY = "/home/dev/data/ai3d/.venv-rig/bin/python"
REQUEST = HERE / "request.json"


def cutout_by_command(who: str, out: Path, tries: int = 3):
    """The cutout through `python -m characters.bridge`, again after a minute if the kit is mid-edit."""
    request = json.loads(REQUEST.read_text())
    request["who"] = who
    out.parent.mkdir(parents=True, exist_ok=True)
    asked = out.parent / f"request-{who}.json"
    asked.write_text(json.dumps(request, indent=1) + "\n")
    for n in range(tries):
        started = time.time()
        done = subprocess.run([sys.executable, "-m", "characters.bridge", str(asked), str(out)], text=True,
                              capture_output=True, cwd=str(HERE.parents[2]))
        print(done.stdout[-600:], done.stderr[-1500:], flush=True)
        if done.returncode == 0:
            return out / "clip.json", time.time() - started, asked
        if n + 1 < tries:
            time.sleep(60)
    return None, 0.0, asked


def set_still(record, out: Path) -> Path:
    """The record's location from the vendored srlocations catalog, through the record's shot."""
    root = Path(json.loads(metadata.distribution("srlocations").read_text("direct_url.json"))["url"][len("file://"):])
    catalog = SharedCatalog.open(root / "catalog")
    entry = catalog.get("location", record.location.name, record.location.version)
    assert entry.digest == record.location.digest, "the catalog's airliner is not the record's"
    cabin = catalog.location(entry.name, entry.version, registry=Registry.default())
    shot = cabin.shots[record.location.shot]      # the same camera as the record's, by its numbers
    ours = bridge.camera_of(shot, record.frame.width, record.frame.height)
    assert ours == record.camera, (ours, record.camera)
    return Renderer(collisions=False).render(cabin, record.location.shot, out, Shaded(record.frame.width, record.frame.height))


def composite(record, folder: Path, still: Path, out: Path) -> tuple[Path, str]:
    """A scene by hand: the set's still, and over it the cutout as an image sequence with straight alpha."""
    w, h, fps = record.frame.width, record.frame.height, int(record.fps)
    scene = Scene(version="auto")
    scene.add_project(width=w, height=h, fps=str(fps), duration=round(record.duration_s, 4), background="#000000")
    assets = scene.add_assets()
    assets.add_image(id="set", src=str(still.resolve()), width=w, height=h)
    assets.add_imageSequence(id="cutout", src=str((folder / record.pattern).resolve()), first=record.first,
                             last=record.last, fps=str(fps), width=w, height=h, alpha="straight")
    layers = scene.add_composition()
    layers.add_layer(id="set-layer", asset="set", x=0, y=0, boxWidth=w, boxHeight=h, fit="cover")
    layers.add_layer(id="cutout-layer", asset="cutout", x=0, y=0, boxWidth=w, boxHeight=h, fit="cover")
    document = out.with_suffix(".scene.xml")
    # written as it is: srlocations.portable.package (characters.clip.package) takes a pattern of numbered frames
    # for one file and refuses it, and this scene has no keys to slim
    document.write_bytes(scene.to_bytes(layout="pretty"))
    engine = str(Renderer(collisions=False).engine)
    for words in (["validate", str(document)],
                  ["encode", str(document), "--hw", "software", "--parallel", "1", "--path", str(out)]):
        done = subprocess.run([engine, *words], text=True, capture_output=True, env=clip.engine_env(False))
        if done.returncode:
            raise SystemExit(done.stdout[-2000:] + done.stderr[-2000:])
    version = subprocess.run([engine, "--version"], text=True, capture_output=True).stdout.strip()
    return out, version


def opaque_frame(request_path: Path, k: int, folder: Path) -> tuple[Path, Path]:
    """Frame `k` of the same film drawn the old way (no alpha, over the backdrop), and its exported geometry."""
    request = bridge.parse_request(request_path.read_bytes())
    f, actor = bridge.from_shot(request["location"], request["shot"], request["mark"], request["who"], request["pose"],
                                int(request["fps"]), facing_deg=request.get("facing_deg"), height_m=request.get("height_m"))
    for a in request["actions"]:
        actor.do(a["at"], a["do"], side=a.get("side") or "right")
    for t in request["takes"]:
        bridge.say_take(actor, t, t["at"])
    f.perform(request["seconds"])
    work = folder / "opaque"
    if work.exists():
        import shutil
        shutil.rmtree(work)
    export.frames(f.loc, "film", work / "export", f.fps, request["seconds"], f.size, first=k, last=k)
    blender.render(work / "export", work / "png", "lowpoly", {**blender.QUALITY["standard"], "scale": 1.0})
    stage = f.stage
    parts = json.loads((work / "export" / f"{k:04d}.json").read_text())["parts"]
    px = [stage.camera.project(stage.to_set(p["verts"][i:i + 3])) for p in parts for i in range(0, len(p["verts"]), 3)]
    box = [min(p[0] for p in px), max(p[0] for p in px), min(p[1] for p in px), max(p[1] for p in px)]
    (folder / "geometry-box.json").write_text(json.dumps({"frame": k, "box_px": box}))
    return work / "png" / f"{k:04d}.png", folder / "geometry-box.json"


def main() -> None:
    out = HERE.parent / "out" / "bridge" / "airliner"
    who, record_path, took, asked = "anchor", None, 0.0, None
    for who in ("anchor", "sergeant"):
        record_path, took, asked = cutout_by_command(who, out / "cutout")
        if record_path:
            break
    if not record_path:
        raise SystemExit("neither anchor nor sergeant could be drawn")
    record = clip_record.load(record_path)
    still = set_still(record, out / "set.png")
    video, engine = composite(record, out / "cutout", still, out / "composite.mp4")
    middle = record.frame_count // 2
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"select=eq(n\\,{middle})", "-frames:v", "1",
                    str(out / "composite-middle.png")], check=True)
    opaque, box = opaque_frame(asked, middle, out)
    facts = {"who": who, "engine": engine, "sr_core": metadata.version("sr-core"), "srlocations": metadata.version("srlocations"),
             "cutout_seconds_whole_command": round(took, 1), "render_log": (out / "cutout" / "render.log").read_text().splitlines()[-4:]}
    (out / "run.json").write_text(json.dumps(facts, indent=1) + "\n")
    subprocess.run([PIL_PY, str(HERE / "measure.py"), str(record_path), str(still), str(out / "composite-middle.png"),
                    str(opaque), str(box), str(out / "measurements.json")], check=True)
    print(json.dumps(facts, indent=1))
    print((out / "measurements.json").read_text())


if __name__ == "__main__":
    main()
