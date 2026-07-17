# -*- coding: utf-8 -*-
"""Afişli PDF'lerin gömülü afişini çıkar → başlık-etiketli montaj PNG'ler.
Her tile: afiş (PDF'ten) + altında TR başlık + yıl + orijinal ad. 5 sütun."""
import fitz, os, re, json, glob, math
from PIL import Image, ImageDraw, ImageFont

KONTROL = r"E:\MITAS\Mitas Output\export\KONTROL"
OUT = r"E:\MITAS\outputs"
fields = json.load(open(os.path.join(OUT,"afis_fields.json"),encoding="utf-8"))

try:
    FONT = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 13)
    FONTB = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 14)
except Exception:
    FONT = FONTB = ImageFont.load_default()

TILE_W, IMG_H = 210, 300
LABEL_H = 64
COLS = 5

def get_poster_pil(path):
    doc = fitz.open(path)
    pg = doc[0]
    best=None; barea=0
    for im in pg.get_images(full=True):
        xref=im[0]
        try:
            px=fitz.Pixmap(doc,xref)
            w,h=px.width,px.height
            if h>w and w*h>20000 and w*h>barea:
                if px.n-px.alpha>3: px=fitz.Pixmap(fitz.csRGB,px)
                mode="RGBA" if px.alpha else "RGB"
                img=Image.frombytes(mode,(w,h),px.samples)
                best=img.convert("RGB"); barea=w*h
            px=None
        except Exception:
            pass
    doc.close()
    return best

def wrap(draw,text,font,maxw):
    words=text.split(); lines=[]; cur=""
    for w in words:
        t=(cur+" "+w).strip()
        if draw.textlength(t,font=font)<=maxw: cur=t
        else:
            if cur: lines.append(cur)
            cur=w
    if cur: lines.append(cur)
    return lines[:3]

def build():
    items=[]
    for p in sorted(glob.glob(os.path.join(KONTROL,"*.pdf"))):
        fn=os.path.basename(p)
        img=get_poster_pil(p)
        if img is None: continue
        d=fields.get(fn,{})
        items.append((fn,img,d))
    print("afişli:",len(items))
    rows=math.ceil(len(items)/COLS)
    PER=20  # montaj başına tile
    nmont=math.ceil(len(items)/PER)
    paths=[]
    for mi in range(nmont):
        chunk=items[mi*PER:(mi+1)*PER]
        r=math.ceil(len(chunk)/COLS)
        W=COLS*TILE_W; H=r*(IMG_H+LABEL_H)
        canvas=Image.new("RGB",(W,H),(245,245,245))
        dr=ImageDraw.Draw(canvas)
        for i,(fn,img,d) in enumerate(chunk):
            cx=(i%COLS)*TILE_W; cy=(i//COLS)*(IMG_H+LABEL_H)
            # afişi tile'a sığdır
            iw,ih=img.size; scale=min((TILE_W-12)/iw, IMG_H/ih)
            nw,nh=int(iw*scale),int(ih*scale)
            thumb=img.resize((nw,nh))
            canvas.paste(thumb,(cx+(TILE_W-nw)//2, cy+(IMG_H-nh)//2))
            # etiket
            gi=mi*PER+i
            title=(d.get("title") or fn)[:40]
            yr=d.get("year") or ""
            sub=(d.get("subtitle") or "")[:30]
            ty=cy+IMG_H+2
            dr.text((cx+4,ty),f"#{gi}",fill=(180,0,0),font=FONTB)
            for ln in wrap(dr,f"{title} ({yr})",FONTB,TILE_W-8):
                dr.text((cx+30,ty),ln,fill=(0,0,0),font=FONTB); ty+=15
            if sub:
                dr.text((cx+4,ty),sub,fill=(90,90,90),font=FONT)
        op=os.path.join(OUT,f"afis_montaj_{mi+1}.png")
        canvas.save(op); paths.append(op)
        print("yazıldı:",op,canvas.size)
    # index dosyası: #gi -> film
    idx={str(gi):{"file":fn,"title":d.get("title"),"year":d.get("year"),
                  "subtitle":d.get("subtitle"),"cast":d.get("cast"),
                  "yonetmen":d.get("yonetmen"),"tur":d.get("tur")}
         for gi,(fn,img,d) in enumerate(items)}
    json.dump(idx,open(os.path.join(OUT,"afis_montaj_index.json"),"w",encoding="utf-8"),
              ensure_ascii=False,indent=1)
    print("index yazıldı")

if __name__=="__main__":
    build()
