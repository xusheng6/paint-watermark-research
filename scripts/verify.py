"""Interoperability checks against captured native DLL outputs."""
import numpy as np
from PIL import Image
import watermark as w
A=w.ROOT/'artifacts'
for name in ['noise','texture']:
 native=np.array(Image.open(A/(name+'.native.png')))
 d=w.decode(native)
 assert d['header_ok'] and d['checksum_ok'] and d['payload']==bytes(range(16)).hex(),name
 replaced=np.array(Image.open(A/(name+'.native_overwrite.png')))
 d=w.decode(replaced)
 assert d['header_ok'] and d['checksum_ok'] and d['payload']==bytes(range(240,256)).hex(),name
 py,_=w.encode(np.array(Image.open(A/(name+'.png'))),bytes(range(16)))
 if name=='noise':assert np.array_equal(py,native)
 d=w.decode(py);assert d['header_ok'] and d['checksum_ok'] and d['payload']==bytes(range(16)).hex(),name
for name in ['gradient','paint_cloud_sample']:
 try:w.encode(np.array(Image.open(A/(name+'.png'))),bytes(range(16)))
 except ValueError as e:assert 'capacity' in str(e)
 else:raise AssertionError(name)
print('PASS: native payloads, native replacements, Python round trips, exact noise reproduction, capacity failures')
