"""Create a submission cover with the actual hosted synthetic spectrum."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parent.parent
r=json.loads((root/'eval/results/aws_demo.json').read_text())
m=r['sessions']['fan-added-mass']['session']['measurement']
im=Image.new('RGB',(1200,630),'#102c2b'); d=ImageDraw.Draw(im)
def f(n,b=False): return ImageFont.truetype('C:/Windows/Fonts/segoeui'+('b' if b else '')+'.ttf',n)
d.rectangle((0,0,1200,8),fill='#95edcc')
d.text((55,45),'OPENCV AI COMPETITION 2026',font=f(17,True),fill='#95edcc')
d.text((55,99),'VibraLens',font=f(76,True),fill='#f2faf7')
d.text((60,202),'See the vibration. Verify the next step.',font=f(31),fill='#d4e8df')
d.text((60,274),'Phone camera  →  OpenCV 5  →  Human-reviewed action',font=f(24),fill='#95edcc')
d.rounded_rectangle((57,337,1142,533),radius=14,fill='#173e3b',outline='#4b796d')
d.text((80,352),'ACTUAL SYNTHETIC DEMO SPECTRUM',font=f(15,True),fill='#95edcc')
freq=m['spectrum']['f']; amp=m['spectrum']['amp_mm']; top=max(amp) or 1
pts=[(80+1035*x/max(freq),510-110*y/top) for x,y in zip(freq,amp)]
d.line(pts,fill='#a6eddd',width=2)
px=80+1035*m['f1x_hz']/max(freq)
d.line((px,389,px,512),fill='#eac079',width=2)
d.text((px+8,392),'24.301 Hz',font=f(18,True),fill='#eac079')
d.text((60,560),'Aakarsh Saxena · Solo developer',font=f(20,True),fill='#f2faf7')
d.text((705,563),'AWS deployed · Synthetic validation',font=f(18),fill='#c0d8d0')
out=root/'docs/screens/submission-cover.png';im.save(out);im.save(root/'web/submission-cover.png')
print(out)
