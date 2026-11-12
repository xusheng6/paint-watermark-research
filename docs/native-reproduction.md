# Reproducing the native DLL experiments

The checked-in PNGs are captures from the documented native DLL. Python verification requires no Windows machine. To obtain fresh native output, supply the precise ARM64 DLL listed in the main report; it is not redistributed here.

1. On a machine with Python dependencies installed, prepare the input buffers:

   ```sh
   python scripts/prepare_native_jobs.py
   ```

2. Copy `native-work` and `scripts/native.ps1` to a Windows ARM64 machine. Use native ARM64 PowerShell in a fresh process. Provide the full DLL path and the full work-directory path:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\native.ps1 -DllPath 'C:\path\to\Watermarker.dll' -WorkDirectory 'C:\path\to\native-work'
   ```

   The execution-policy option applies to this process. The harness reads the DLL, checks its hash, and loads it; it does not patch it or change the installed Paint application. The tree and DCT offsets are specific to this exact hash. The new portable wrapper was prepared for publication; the captured evidence came from the original Parallels/PInvoke harness described in the report. This wrapper has not been rerun in Windows since the VM was shut down.

3. Inspect `native_results.json`: the four initial jobs should return `0,0,-8,-8`; the two replacement jobs should return `0`. Only successful jobs produce output buffers. The replacement jobs use the already watermarked, checked-in captures as input; they do not depend on reusing failed-job buffers.

4. Each successful `.argb` file contains 512×512 pixels in A,R,G,B byte order. Convert a capture to RGB PNG for the Python decoder:

   ```python
   import numpy as np
   from PIL import Image
   a = np.fromfile('native-work/texture.argb', dtype=np.uint8).reshape(512,512,4)
   Image.fromarray(a[...,1:]).save('native-work/texture.png')
   ```

   ```sh
   python scripts/watermark.py decode native-work/texture.png
   ```

The expected initial payload is `000102030405060708090a0b0c0d0e0f`; the replacement is `f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff`. A successful decode should also pass the header and checksum checks. This verifies the research decoder, not Microsoft's private detector.

The tree dump contains twelve groups of five vectors. Each vector begins with a signed 32-bit byte length followed by that many bytes. Vector types are little-endian int32, int32, float64, int32, float64. `artifacts/trees.json` is the readable representation extracted during the original run. The 128-byte DCT dump contains sixteen little-endian doubles, initialized by the DLL on load.
