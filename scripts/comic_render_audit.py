# Render audit: crop every caption/SFX from the actual rendered mp4s (mapped through zoom + shake) into contact sheets for a visual sliced-lettering check. Paths are for the Neon Dojo v4 renders; edit vids/OUT for other projects.
import sys,subprocess,numpy as np
sys.path.insert(0,'scripts')
import comic_lib as C
from PIL import Image,ImageDraw
spec=C.load_spec('shots/neon-dojo-comic/neon-dojo-comic-v3.comic.json')
OUT='/workspace/neon-dojo-comic/out/'
vids={'landscape':(OUT+'neon-dojo-comic-1080p-v5.mp4',0.0,999),'vertical':(OUT+'neon-dojo-comic-short-v5.mp4',112.25,155.81)}
def frame(p,t,W,H):
    b=subprocess.run(['ffmpeg','-v','error','-ss',f'{t:.3f}','-i',p,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
    return Image.frombytes('RGB',(W,H),b)
crops={'landscape':[],'vertical':[]};edge=[]
for sub in C.subspecs(spec):
  for orient in ('landscape','vertical'):
    W,H=C.SIZES[orient]; p,a,b=vids[orient]
    sc=C.Scene(sub,orient)
    tr=sub.get('transition')
    for it in C.text_items(sub,orient):
      for dt in ((0.12,0.45) if it.get('kind')=='sfx' else (0.35,)):
        t=it['from']+dt
        if t>=it['to']: continue
        g=t+sub['song']['start']
        if not(a<=g<b-0.05): continue
        vb=sc.view_box(t); shb=sc.shake_box(t)
        if tr and vb!=(0,0,W,H) and it['unit']!=tr['panel']: continue
        x,y,w,h=it['rect'];sx_=W/vb[2];sy_=H/vb[3]
        r=[(x-vb[0])*sx_,(y-vb[1])*sy_,w*sx_,h*sy_]
        if shb: r=[(r[0]-shb[0])*W/shb[2],(r[1]-shb[1])*H/shb[3],r[2]*W/shb[2],r[3]*H/shb[3]]
        if r[0]<2 or r[1]<2 or r[0]+r[2]>W-2 or r[1]+r[3]>H-2: edge.append((orient,it['who'],g))
        f=frame(p,g-a,W,H); m=24
        c=f.crop((max(0,int(r[0]-m)),max(0,int(r[1]-m)),min(W,int(r[0]+r[2]+m)),min(H,int(r[1]+r[3]+m))))
        crops[orient].append((f"{sub.get('page')} {it['who']} {g:.2f}s",c))
print('edge',edge)
for orient,L in crops.items():
  print(orient,len(L))
  for k in range(0,len(L),12):
    ch=L[k:k+12]; tw=440
    rows=[(lbl,c.resize((tw,max(1,int(c.height*tw/c.width))))) for lbl,c in ch]
    Hh=sum(c.height+22 for _,c in rows[::2])+sum(0 for _ in rows)
    sheet=Image.new('RGB',(2*(tw+10),sum(max(r[1].height for r in rows[i:i+2])+22 for i in range(0,len(rows),2))),(30,30,30));d=ImageDraw.Draw(sheet);y=0
    for i in range(0,len(rows),2):
      hh=0
      for j,(lbl,c) in enumerate(rows[i:i+2]):
        sheet.paste(c,(j*(tw+10),y+20));d.text((j*(tw+10)+2,y+4),lbl[:70],fill='yellow');hh=max(hh,c.height)
      y+=hh+22
    sheet.save(f'{OUT}v5-audit/{orient}-{k//12:02d}.png')
