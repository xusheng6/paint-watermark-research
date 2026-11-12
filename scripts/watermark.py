"""Recovered local Paint Watermarker.dll transform and experimental blind decoder.
Payload bytes are raw DLL bytes; GUID display byte order is a caller concern.
"""
from pathlib import Path
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
T=np.fromfile(ROOT/'artifacts/dct.bin',dtype='<f8').reshape(4,4)/np.sqrt(2)
T[0]/=np.sqrt(2)
TREES=json.loads((ROOT/'artifacts/trees.json').read_text())
def ycc(rgb):
 r,g,b=np.asarray(rgb,dtype=float).transpose(2,0,1)
 return .299*r+.587*g+.114*b,128-.169*r-.331*g+.5*b,128+.5*r-.419*g-.081*b
def rgb_from(y,cb,cr):
 return np.clip(np.stack([y+1.4*(cr-128),y-.343*(cb-128)-.711*(cr-128),y+1.765*(cb-128)],-1),0,255).astype('uint8')
def transform(rgb):
 y,cb,cr=ycc(rgb); h,w=np.array(y.shape)//8*8
 p=y[:h,:w].reshape(h//2,2,w//2,2)
 ll=p.sum((1,3))*.5
 blocks=ll.reshape(h//8,4,w//8,4).transpose(0,2,1,3)
 d=T@blocks@T.T
 return y,cb,cr,ll,d
def matrices(d):return d.reshape(*d.shape[:2],16)[...,1:].reshape(*d.shape[:2],3,5)
def schedule(h,w):
 return ((np.arange(h)[:,None]%12)*12+np.arange(w)[None,:]%12)
def message(payload):
 if len(payload)!=16:raise ValueError('16 bytes required')
 return bytes([0x4c])+payload+bytes([sum(payload)%256])
def predict(features):
 shape=features.shape[:-1];f=features.reshape(-1,features.shape[-1]);score=np.zeros(len(f))
 for left,right,value,feat,thresh in TREES:
  n=np.zeros(len(f),int)
  while np.any(n>=0):
   ix=np.flatnonzero(n>=0);k=n[ix]
   n[ix]=np.where(f[ix,np.array(feat)[k]]<=np.array(thresh)[k],np.array(right)[k],np.array(left)[k])
  score+=np.array(value)[~n]
 return score.reshape(shape)
def encode(rgb,payload,gate=True,require_capacity=True):
 rgb=np.asarray(rgb)
 if rgb.ndim!=3 or rgb.shape[2]!=3 or min(rgb.shape[:2])<192:
  raise ValueError("RGB image with width and height at least 192 required")
 y,cb,cr,ll,d=transform(rgb); m=matrices(d);u,s,v=np.linalg.svd(m,full_matrices=False);original_s=s[...,0].copy()
 bits=np.unpackbits(np.frombuffer(message(payload),dtype='uint8'));idx=schedule(*m.shape[:2])
 s[...,0]=(np.floor(s[...,0]/24)+.25+.5*bits[idx])*24
 out=(u*s[...,None,:])@v
 features=np.concatenate([original_s[...,None],s[...,:1],m.reshape(*idx.shape,15),out.reshape(*idx.shape,15)],-1)
 score=predict(features); mask=score<=.2 if gate else np.ones(idx.shape,bool)
 counts=np.bincount(idx[mask],minlength=144)
 if require_capacity and counts.min()<3:
  raise ValueError('Insufficient capacity: native DLL returns -8')
 md=np.where(mask[...,None,None],out,m)
 nd=d.copy().reshape(*idx.shape,16);nd[...,1:]=md.reshape(*idx.shape,15)
 b=T.T@nd.reshape(d.shape)@T
 nll=b.transpose(0,2,1,3).reshape(ll.shape)
 delta=(nll-ll)*.5
 yy=y.copy();hh,ww=ll.shape;yy[:hh*2,:ww*2]+=np.repeat(np.repeat(delta,2,0),2,1)
 return rgb_from(yy,cb,cr),{'counts':counts,'mask':mask,'score':score,'original_sigma':original_s,'features':features}
def decode(rgb):
 *_,d=transform(rgb);m=matrices(d);s=np.linalg.svd(m,compute_uv=False)[...,0];idx=schedule(*s.shape)
 # Use distance from the quantizer decision boundary as soft evidence.
 phase=s%24; evidence=np.sin((phase-12)*np.pi/12)
 sums=np.bincount(idx.ravel(),weights=evidence.ravel(),minlength=144)
 bits=sums>0;msg=np.packbits(bits).tobytes()
 return {'message':msg.hex(),'payload':msg[1:17].hex(),'header_ok':msg[0]==0x4c,'checksum_ok':sum(msg[1:17])%256==msg[17],'bits':bits,'scores':sums}

if __name__=='__main__':
 import argparse
 from PIL import Image
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('mode',choices=['encode','decode','erase'])
 p.add_argument('input');p.add_argument('--output');p.add_argument('--payload',help='16 raw bytes as 32 hex digits')
 args=p.parse_args();im=np.array(Image.open(args.input).convert('RGB'))
 if args.mode=='decode':
  print(json.dumps({k:v for k,v in decode(im).items() if k not in ('bits','scores')},indent=2))
 else:
  if not args.output:p.error('--output required')
  if args.mode=='encode':
   if not args.payload:p.error('--payload required')
   out,_=encode(im,bytes.fromhex(args.payload))
  else:
   from experiments import erase
   out=erase(im)
  Image.fromarray(out).save(args.output)
