"""Build self-contained native harness inputs from the checked-in fixtures."""
import argparse
import base64
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, default=ROOT/'native-work')
args = p.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
jobs = []
for name in ['noise', 'texture', 'gradient', 'paint_cloud_sample']:
    rgb = np.array(Image.open(ROOT/'artifacts'/(name+'.png')).convert('RGB'))
    h, w = rgb.shape[:2]
    argb = np.concatenate([np.full((h,w,1),255,dtype='uint8'),rgb],axis=2)
    input_name = name+'.input'
    (args.output/input_name).write_bytes(argb.tobytes())
    jobs.append(dict(name=name, input=input_name, payload=base64.b64encode(bytes(range(16))).decode(),w=w,h=h))
for name in ['noise', 'texture']:
    rgb = np.array(Image.open(ROOT/'artifacts'/(name+'.native.png')).convert('RGB'))
    h,w = rgb.shape[:2]
    input_name = name+'.native.input'
    argb = np.concatenate([np.full((h,w,1),255,dtype='uint8'),rgb],axis=2)
    (args.output/input_name).write_bytes(argb.tobytes())
    jobs.append(dict(name=name+'_native_overwrite',input=input_name,payload=base64.b64encode(bytes(range(240,256))).decode(),w=w,h=h))
(args.output/'jobs.json').write_text(json.dumps(jobs,indent=2))
print(f'Prepared {len(jobs)} jobs in {args.output}')
