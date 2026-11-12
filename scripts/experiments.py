import io,json,sys,hashlib
import numpy as np
from PIL import Image,ImageFilter
import watermark as wm
from pathlib import Path
ROOT=wm.ROOT;A=ROOT/'artifacts';rng=np.random.default_rng(2384)
payload=bytes(range(16));expected=np.unpackbits(np.frombuffer(wm.message(payload),dtype='uint8'));replacement=bytes(range(240,256))
def metrics(a,b):
 if a.shape!=b.shape:return {}
 mse=np.mean((a.astype(float)-b.astype(float))**2)
 return dict(psnr_db=float(10*np.log10(255**2/mse)) if mse else None,mean_abs_error=float(np.abs(a.astype(float)-b).mean()))
def evaluate(name,attack,a,b):
 d=wm.decode(b);return dict(image=name,attack=attack,payload=d['payload'],header_ok=d['header_ok'],checksum_ok=d['checksum_ok'],message_bit_errors=int(np.count_nonzero(d['bits']!=expected)),original_recovered=d['payload']==payload.hex(),**metrics(a,b))
def erase(a):
 y,cb,cr,ll,d=wm.transform(a);m=wm.matrices(d);u,s,v=np.linalg.svd(m,full_matrices=False)
 # Randomize quantizer phase with no original image or payload knowledge.
 s[...,0]=np.floor(s[...,0]/24)*24+rng.uniform(0,24,s.shape[:2])
 out=(u*s[...,None,:])@v;nd=d.copy().reshape(*d.shape[:2],16);nd[...,1:]=out.reshape(*d.shape[:2],15)
 blocks=wm.T.T@nd.reshape(d.shape)@wm.T;nll=blocks.transpose(0,2,1,3).reshape(ll.shape)
 h,w=ll.shape;y[:h*2,:w*2]+=np.repeat(np.repeat((nll-ll)*.5,2,0),2,1)
 return wm.rgb_from(y,cb,cr)
if __name__=='__main__':
 rows=[];validation=[]
 for name in ['noise','texture']:
  # Preserve the original random-stream slot for each retained fixture.
  rng=np.random.default_rng(2384)
  for _ in range({'noise':0,'texture':2}[name]):
   rng.normal(0,1,(512,512,3));rng.uniform(0,24,(64,64))
  src=np.array(Image.open(A/(name+'.png')))
  native=np.array(Image.open(A/(name+'.native.png')).convert('RGB'))
  py,diag=wm.encode(src,payload)
  validation.append(dict(image=name,minimum_placements=int(diag['counts'].min()),selected_blocks=int(diag['mask'].sum()),unequal_channels=int(np.count_nonzero(py!=native)),maximum_channel_difference=int(np.abs(py.astype(int)-native).max()),**metrics(src,native)))
  attacks={'unaltered':native,'metadata_free_png':np.array(Image.open(A/(name+'.native.png'))),'roll_x1':np.roll(native,1,axis=1),'roll_x8':np.roll(native,8,axis=1),'roll_x96':np.roll(native,96,axis=1),'crop_8':native[8:-8,8:-8],'resize_half':np.array(Image.fromarray(native).resize((256,256),Image.Resampling.LANCZOS)),'resize_half_restore':np.array(Image.fromarray(native).resize((256,256),Image.Resampling.LANCZOS).resize((512,512),Image.Resampling.LANCZOS)),'gaussian_blur_0.5':np.array(Image.fromarray(native).filter(ImageFilter.GaussianBlur(.5))),'gaussian_noise_1':np.clip(native.astype(float)+rng.normal(0,1,native.shape),0,255).astype('uint8'),'randomize_singular_phase':erase(native),'replace_payload_python':wm.encode(native,replacement,gate=False)[0]}
  for q in [100,95,90,80,70]:
   buf=io.BytesIO();Image.fromarray(native).save(buf,format='JPEG',quality=q);buf.seek(0);attacks['jpeg_'+str(q)]=np.array(Image.open(buf))
  for attack,b in attacks.items():
   rows.append(evaluate(name,attack,native,b))
   if attack in ['randomize_singular_phase','replace_payload_python']:Image.fromarray(b).save(A/(name+'.'+attack+'.png'))
 (A/'experiment_results.json').write_text(json.dumps(rows,indent=2));(A/'validation.json').write_text(json.dumps(validation,indent=2))
 for v in validation:print(v)
 for r in rows:
  if r['image']=='texture': print(r['attack'],r['message_bit_errors'],r['header_ok'],r['checksum_ok'],round(r.get('psnr_db') or 0,2),r['payload'])
