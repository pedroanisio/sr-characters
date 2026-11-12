#!/bin/bash
# one round: proofs of the people named (default all five), comparison with the sheet, outline score with the
# differences by body band and the cloth surface ratio (all of it in $S/sergeant-match.json), close-ups
S=${OUT:-/tmp/lowpoly-round}; mkdir -p $S; PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python; V=/home/dev/data/ai3d/.venv-rig/bin/python
cd /home/dev/data/sr-data; O=characters/examples/out
WHO="${@:-sergeant cook firefighter captain anchor}"
for who in $WHO; do $PY characters/lowpoly3d.py proof $who 2>&1 | grep -v "guard\|FRAMES done" | tail -2; done
$V characters/tools/lowpoly/sheet_match.py characters/tools/lowpoly/ref/officer-sheet.png $O/lowpoly-sergeant-front.png $O/lowpoly-sergeant-profile.png $O/lowpoly-sergeant-back.png $O/lowpoly-sergeant-outline.png --widths --surface --brief --json $S/sergeant-match.json
$V - <<P
from PIL import Image
O='$O/'; S='$S/'
t=[Image.open(O+'lowpoly-%s.png'%w) for w in ("sergeant","cook","firefighter","captain","anchor")]
s=Image.new('RGB',(t[0].width,sum(i.height for i in t))); y=0
for i in t: s.paste(i,(0,y)); y+=i.height
s.save(O+'lowpoly-people.png')
for w in '$WHO'.split():
    a=Image.open(O+'lowpoly-%s-profile.png'%w).crop((200,60,520,440)).resize((800,950),Image.LANCZOS)
    b=Image.open(O+'lowpoly-%s-front.png'%w).crop((200,60,520,440)).resize((800,950),Image.LANCZOS)
    c=Image.open(O+'lowpoly-%s-back.png'%w).crop((200,60,520,440)).resize((800,950),Image.LANCZOS)
    h=Image.new('RGB',(2400,950)); h.paste(b,(0,0)); h.paste(a,(800,0)); h.paste(c,(1600,0)); h.save(S+w+'-heads.png')
P
