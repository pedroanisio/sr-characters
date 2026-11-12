import sys
sys.path.insert(0, "/home/dev/data/sr-data")
from characters import film
from characters.poses import POSES
who, out = sys.argv[1], sys.argv[2]
names = list(POSES[who])[:16]
for row in range(2):
    f = film.Film(f"lp-poses-{row}", size=(2000, 560))
    for i, n in enumerate(names[row * 8:row * 8 + 8]):
        f.add(who, n, at=((i - 3.5) * 0.62, 0, 0), yaw=-15, name=f"{who}{i}")
    f.camera((0.0, 0.6, 9.0), look_at=(0, 0.52, 0), lens=62)      # all eight in the frame
    f.still(f"{out}-{row}.png", finish="lowpoly", quality="standard")
print("poses", names)
