import sys
from PIL import Image
d, name = sys.argv[1], sys.argv[2]
ref = Image.open('/home/dev/data/sr-data/characters/tools/lowpoly/ref/officer-sheet.png').convert('RGB').crop((100, 40, 1436, 940))
t = [Image.open(f'{d}/{name}-{v}.png').convert('RGB') for v in ('front', 'profile', 'back')]
h = 600
t = [i.resize((i.width * h // i.height, h)) for i in t]
w = sum(i.width for i in t)
r = ref.resize((w, ref.height * w // ref.width))
s = Image.new('RGB', (w, r.height + h), (253, 236, 217))
s.paste(r, (0, 0)); x = 0
for i in t:
    s.paste(i, (x, r.height)); x += i.width
s.save(f'{d}/{name}-compare.png')
