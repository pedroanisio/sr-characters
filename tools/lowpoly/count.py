import sys, glob, shutil
sys.path.insert(0, "/home/dev/data/sr-data")
from characters import film
out = sys.argv[1]
for who in sys.argv[2:]:
    shutil.rmtree(f"{out}/count-{who}.frames", ignore_errors=True)     # frames already drawn are skipped, and say nothing
    f = film.Film("count-" + who, size=(540, 810))
    f.add(who, "idle", at=(0, 0, 0))
    f.camera((0.0, 0.58, 6.0), look_at=(0, 0.56, 0), lens=118)
    f.render(f"{out}/count-{who}.mp4", seconds=0.09, finish="lowpoly", quality="draft")
    for log in glob.glob(f"{out}/count-{who}.frames/*.log"):
        for line in open(log):
            if "triangles" in line:
                print(who, line.strip())
