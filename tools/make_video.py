"""Render a narrated evidence video from real synthetic inputs and verified results."""
from pathlib import Path
import json
import subprocess
import sys
import wave
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'video' / 'build'
BUILD.mkdir(exist_ok=True, parents=True)
scenes = json.loads((ROOT / 'video/scenes.json').read_text(encoding='utf-8'))
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
FONT = Path('C:/Windows/Fonts/segoeui.ttf')
BOLD = Path('C:/Windows/Fonts/segoeuib.ttf')
def font(size, bold=False):
    return ImageFont.truetype(str(BOLD if bold else FONT), size)
def wrapped(draw, text, xy, width, face, fill, spacing=12):
    x, y = xy
    line = ''
    for word in text.split():
        proposed = (line + ' ' + word).strip()
        if draw.textlength(proposed, font=face) > width and line:
            draw.text((x,y), line, font=face, fill=fill)
            y += face.size + spacing
            line = word
        else:
            line = proposed
    draw.text((x,y), line, font=face, fill=fill)
    return y + face.size + spacing

durations = []
for i, scene in enumerate(scenes):
    with wave.open(str(BUILD / f'scene-{i}.wav')) as audio:
        duration = audio.getnframes() / audio.getframerate() + 1.0
    durations.append(duration)
    im = Image.new('RGB', (1280,720), '#0d2425')
    d = ImageDraw.Draw(im)
    d.rectangle((0,0,1280,7), fill='#97ebca')
    d.text((55,40), 'VIBRALENS / OPENCV 5', font=font(17,True), fill='#97ebca')
    d.text((1170,40), f'0{i+1} / 07', font=font(16), fill='#b8d2cd')
    y = wrapped(d, scene['title'], (55,97), 1120, font(43,True), '#f2faf6')
    wrapped(d, scene['subtitle'], (55,y+4), 1140, font(23), '#b8d2cd')
    y = 272
    for bullet in ([] if scene.get('architecture') else scene['bullets']):
        d.ellipse((58,y+12,65,y+19),fill='#97ebca')
        y = wrapped(d,bullet,(83,y),545 if scene['sample'] or scene.get('screenshot') else 1090,font(25),'#eef6f3',10)+17
    if scene.get('architecture'):
        nodes = [(55,270,'Phone browser','Original slow-motion capture'),
                 (455,270,'CloudFront','HTTPS judge endpoint'),
                 (855,270,'EC2 / OpenCV 5','Quality + motion + agent policy'),
                 (55,445,'S3','Private video evidence'),
                 (455,445,'DynamoDB','Sessions, readings, leased jobs'),
                 (855,445,'SNS + human','Approval before maintenance')]
        for x,y,label,detail in nodes:
            d.rounded_rectangle((x,y,x+350,y+115),radius=12,fill='#173e3b',outline='#578f7e',width=2)
            d.text((x+18,y+16),label,font=font(25,True),fill='#97ebca')
            wrapped(d,detail,(x+18,y+59),315,font(17),'#eef6f3',4)
        for x in (410,810):
            d.line((x,326,x+35,326),fill='#97ebca',width=3)
            d.polygon([(x+35,326),(x+26,320),(x+26,332)],fill='#97ebca')
        d.line((1030,391,1030,435),fill='#97ebca',width=3)
        d.line((230,426,1030,426),fill='#97ebca',width=2)
        d.line((230,426,230,439),fill='#97ebca',width=2)
        d.line((630,426,630,439),fill='#97ebca',width=2)
    if scene.get('screenshot'):
        screen = Image.open(ROOT / 'video' / scene['screenshot']).convert('RGB')
        wide = screen.width > screen.height * 1.2
        screen.thumbnail((545 if wide else 350,365))
        im.paste(screen,(680 if wide else 850,255))
        label = 'LIVE APPLICATION / AWS' if scene['screenshot'].startswith('aws-') else 'LIVE APPLICATION / LOCALHOST'
        d.text((688 if wide else 820,625),label,font=font(15,True),fill='#97ebca')
    if scene['sample']:
        d.rounded_rectangle((680,271,1225,581),radius=14,fill='#173e3b')
        d.text((688,600),'ACTUAL SYNTHETIC INPUT / NOT FIELD FOOTAGE',font=font(15,True),fill='#97ebca')
    elif not scene.get('screenshot') and not scene.get('architecture'):
        d.text((60,590),'LOCAL EXECUTION VERIFIED  /  AWS DEPLOYMENT PENDING',font=font(17,True),fill='#97ebca')
    d.line((55,656,1225,656),fill='#355450',width=1)
    d.text((55,675),'Aakarsh Saxena | Solo entrant',font=font(16),fill='#b8d2cd')
    d.text((795,675),'Synthetic evaluation • Computer-generated narration',font=font(14),fill='#b8d2cd')
    still = BUILD / f'scene-{i}.png'
    im.save(still)
    args = [ffmpeg,'-y','-loop','1','-framerate','15','-i',str(still)]
    if scene['sample']:
        args += ['-stream_loop','-1','-i',str(ROOT/'samples'/scene['sample']),'-i',str(BUILD/f'scene-{i}.wav'),
                 '-filter_complex','[1:v]fps=15,scale=524:294:force_original_aspect_ratio=decrease,pad=526:298:(ow-iw)/2:(oh-ih)/2:color=0x173e3b[v];[0:v][v]overlay=690:278[out]',
                 '-map','[out]','-map','2:a']
    else:
        args += ['-i',str(BUILD/f'scene-{i}.wav'),'-map','0:v','-map','1:a']
    args += ['-t',str(duration),'-r','15','-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p',
             '-c:a','aac','-ar','44100','-ac','2','-af','apad','-movflags','+faststart',str(BUILD/f'scene-{i}.mp4')]
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    print(f'Rendered scene {i+1}: {duration:.1f}s',flush=True)
assert sum(durations) < 300, 'Video exceeds competition limit'
(BUILD/'concat.txt').write_text('\n'.join(f"file 'scene-{i}.mp4'" for i in range(len(scenes))),encoding='utf-8')
out = ROOT/'video/VibraLens-demo.mp4'
subprocess.run([ffmpeg,'-y','-f','concat','-safe','0','-i',str(BUILD/'concat.txt'),'-c','copy','-movflags','+faststart',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
(ROOT/'video/transcript.txt').write_text('\n\n'.join(s['narration'] for s in scenes),encoding='utf-8')
print(f'Video ready: {out} | {sum(durations):.1f} seconds')
