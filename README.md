# Microsoft Paint watermark algorithm and security evaluation

Paint's local `Watermarker.dll` embeds a public, repeatable 144-bit message in image luminance using Haar DWT, block DCT, SVD, and quantization. Its payload is neither encrypted nor authenticated by this DLL. The unmodified DLL can overwrite an existing watermark with a chosen replacement payload. A Python implementation and experimental blind decoder recover both original and replacement payloads from native DLL outputs.

The local algorithm belongs to the established DWT–DCT–SVD watermarking family, with product-specific coefficient packing, message framing, spatial repetition, and a decision-tree selection model. This does **not** establish that it is Microsoft's published neural InvisMark algorithm. Cloud-image manifest naming does not identify the local implementation.

## Target and evidence

Tested on 12 November 2026 in the existing Parallels Windows 11 ARM64 VM:

- Paint package: `Microsoft.Paint_11.2605.81.0_arm64__8wekyb3d8bbwe`.
- DLL path: `C:\Program Files\WindowsApps\Microsoft.Paint_11.2605.81.0_arm64__8wekyb3d8bbwe\PaintApp\Watermarker.dll`.
- File version: `1.2502.1`; product version `1.2502.1`.
- Size: 1,225,216 bytes.
- SHA-256: `a9c41377c6e8f49d911eca452cc28ad18f33249733ab529afea2120fe0aa3b43`.
- A pre-existing host copy and the installed guest DLL have the same SHA-256.
- Only exported watermark function: `WmkWriteWatermark`, preferred VA `0x180004750`, RVA `0x4750`.

The tests call the DLL directly with controlled pixels and payloads. They do not require AI generation, network moderation, or account credentials. Standard embedding and overwrite experiments use the unmodified DLL. A separate instrumented process captures initialized constants, model data, and intermediate features; instrumentation changes process memory in a disposable loaded copy, not the installed file.

The local DLL is software, rather than firmware. This study covers this precise build and its RGB embedding path. It does not establish that a different x64 release, Photos release, or cloud service uses an identical encoder.

## Recovered embedding process

### Input and message

The recovered call boundary is:

```c
int WmkWriteWatermark(
    uint8_t *output, const uint8_t *payload, uint64_t payload_length,
    int32_t width, int32_t height, int32_t stride,
    const uint8_t *input, int pixel_format);
```

The harness uses format `1`, with byte order **A, R, G, B**. This is not ordinary BGRA byte order. It uses opaque alpha and positive stride. The DLL also has paths for formats 3 and 4; the supplied Python tool implements RGB images, not those complete buffer/alpha conventions.

Payload length must be exactly 16. The DLL frames those bytes as:

```text
0x4c | payload[16] | sum(payload) mod 256
```

It expands each byte most-significant-bit first, producing 144 bits. There is no BCH or other payload ECC stage in this recovered write path; redundancy comes from spatial repetition. The checksum detects some accidental errors but is trivial to recompute. The DLL does not check that the supplied bytes constitute a server-issued or otherwise authorized GUID.

Widths and heights must each be at least 192. The working region is rounded down to multiples of eight. A failed placement-capacity check returns `-8`; caller output from that failure must not be treated as a watermarked image.

### Transforms and coefficient packing

1. Convert RGB to luminance and two chroma planes, in double precision:

   ```text
   Y  =  .299 R + .587 G + .114 B
   Cb = 128 - .169 R - .331 G + .500 B
   Cr = 128 + .500 R - .419 G - .081 B
   ```

2. Apply one level of Haar DWT to Y. The LL coefficient for each 2×2 pixel group is half its sum. Preserve the other three bands.
3. Apply a normalized 4×4 DCT to blocks of LL. Each block therefore covers 8×8 source pixels.
4. Leave the DCT DC coefficient unchanged. Flatten the remaining 15 coefficients in row order and pack them into a **3×5 matrix**. SVD operates on this packed matrix, rather than the entire 4×4 DCT block.
5. Decompose that matrix into `U, singular_values, Vt` and quantize its largest singular value.

For message bit `b`, step size is 24 and the replacement is:

```text
s0_new = (floor(s0 / 24) + 0.25 + 0.5*b) * 24
```

A zero selects phase 6 modulo 24; a one selects phase 18. A natural blind decision boundary is phase 12. The Python decoder combines soft evidence from repeated placements rather than relying on a single block.

### Spatial schedule and selection model

For 8×8 source-block coordinates `(r,c)`, the message index is:

```text
bit_index = 12*(r mod 12) + (c mod 12)
```

Thus the entire 144-bit message repeats in a **96×96 source-pixel tile**. This schedule is fixed and public in the code; it has no per-image secret permutation or key.

Before committing a candidate block, the encoder evaluates twelve regression-style decision trees. Each tree has 19 internal nodes and 20 leaf values. Tree vectors are left child, right child, leaf values, feature indices, and thresholds. A negative child encodes a leaf using bitwise complement. The DLL sums the twelve leaf outputs and accepts the block when the sum is at most 0.2.

The 32 features are the original largest singular value, its quantized replacement, 15 original matrix coefficients, and 15 reconstructed coefficients. This is a learned-looking selection model around a classical embedding transform; its exact training objective and provenance are not established. It likely selects blocks expected to be usable or acceptable, but calling it a particular perceptual or robustness classifier would require more evidence.

The write succeeds only if **every message bit has at least three accepted placements**. It then restores the packed coefficients, performs inverse DCT and inverse Haar reconstruction, and converts Y/Cb/Cr back to RGB with clipping and integer truncation. The inverse conversion uses approximate coefficients `1.4`, `.343`, `.711`, and `1.765`, so some pixel changes come from color round trips as well as embedding.

## Implementation and validation

- [scripts/watermark.py](scripts/watermark.py): Python embedding pipeline, extracted decision trees, experimental blind decoder, and CLI.
- [scripts/native.ps1](scripts/native.ps1): ARM64 PowerShell/C# P/Invoke harness for the actual DLL.
- [scripts/experiments.py](scripts/experiments.py): image transformations, phase-randomization experiment, and measurements.
- [scripts/verify.py](scripts/verify.py): native interoperability checks.
- [artifacts/trees.json](artifacts/trees.json), [artifacts/dct.bin](artifacts/dct.bin): initialized model and DCT constants extracted from a loaded DLL.
- [docs/reverse-engineering.md](docs/reverse-engineering.md): address map and evidence notes.

All principal images are 512×512. `noise` is seeded RGB noise; `texture` is a resized pre-existing Paint image plus seeded Gaussian noise of standard deviation 12. This is a small mechanism-validation corpus, not a representative watermark benchmark. The historical fixture name `paint_cloud_sample` refers to a pre-existing Paint canvas image (a line drawing). Its cloud-generation provenance was not revalidated; it is used only as input pixels, with no algorithm equivalence inferred.

Native embedding of payload `000102030405060708090a0b0c0d0e0f` succeeded on both images. The experimental Python decoder recovered the entire 18-byte framed message with **zero bit errors** on both native outputs.

| Image | Python selected blocks | Python minimum placements per bit | Python vs native unequal RGB channels | Native watermark PSNR vs input |
| --- | ---: | ---: | ---: |
| Noise | 4096 | 25 | 0 of 786432 | 45.81 dB |
| Textured sample | 4074 | 24 | 213 of 786432 | 46.99 dB |

Noise output is byte-for-byte identical. The Python implementation is **not a universally bit-exact clone**: Texture has a maximum channel discrepancy of 1. Nearly flat/rank-deficient blocks are sensitive to numerical residuals and SVD basis choices, and the selection trees can amplify resulting differences. The remaining numerical discrepancies have not been eliminated. Python output nonetheless round-trips the chosen payload on both images.

The DLL returned `-8` for the smooth gradient and the smooth resized Paint canvas fixture. The Python capacity checks agree that some bits lack the required placements. This is an encoder limitation even for images larger than the minimum dimensions.

## Resilience and deliberate modification

All recovery claims below refer to the supplied experimental decoder. The DLL exports no reader, and Microsoft's private detector and any server-side lookup policy were not available for validation.

### Ordinary edits

| Operation | Noise message errors | Texture message errors |
| --- | ---: | ---: |
| PNG re-save without metadata | 0 | 0 |
| JPEG quality 90 | 0 | 0 |
| JPEG quality 70 | 0 | 13 |
| Half-size then restore original size | 68 | 8 |

These are errors across all 144 bits, including header and checksum. Results vary with image content. These two synthetic fixtures do not establish performance on photographs or other real-world images.

One-pixel shifts and crops break the current decoder's assumed grid alignment. They are **not demonstrated irreversible removal**: searching translations or restoring geometry can recover a mark. A cyclic 96-pixel horizontal shift preserves recovery on both images, as predicted by the repeated tile schedule. The decoder does not implement Microsoft's possible synchronization, scale search, or crop recovery strategies.

### Targeted phase randomization

The `erase` experiment changes each block's dominant singular-value remainder to a seeded random phase in `[0,24)`, preserving its quantization-bin index and the DC coefficient. It requires neither the original image nor knowledge of the original payload.

| Image | Message errors after phase randomization | PSNR relative to native watermarked image |
| --- | ---: | ---: |
| Noise | 75 / 144 | 45.82 dB |
| Texture | 65 / 144 | 46.93 dB |

Both fail both header and checksum checks. This demonstrates low-distortion disruption of the recovered channel and this decoder, not a measured false-negative rate for Microsoft's undisclosed detector. It does not restore the exact pre-watermark image.

### Payload replacement through the unmodified DLL

The stronger integrity result does not depend on a Python encoder approximation. Calling the original DLL a second time, on the already watermarked pixels, with payload `f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff` returns success on both images. The Python decoder recovers that replacement exactly, with a valid header and checksum.

| Image | New payload recovered exactly | Replacement PSNR relative to first watermark |
| --- | --- | ---: |
| Noise | Yes | 46.52 dB |
| Texture | Yes | 48.33 dB |

Python can also replace the payload in both images by quantizing all candidate blocks, without the DLL. This experiment deliberately disables the placement gate; it is an attack tool, not a faithful simulation of the native encoder's block policy.

An attacker choosing the payload can satisfy the additive checksum immediately. No embedded MAC, signature, encryption key, or server authorization is checked by this write API. Consequently the pixel watermark alone does not authenticate an image or an attribution identifier. This does **not** forge a Microsoft-signed C2PA manifest, prove a chosen identifier has a server-side record, or show that a verifier would accept a pixel/manifest mismatch. The cryptographic provenance layer must be evaluated separately.

## Known algorithm or in-house design

The quantization formula and transform family have close public precedents. The `invisible-watermark` project's `dwtDctSvd.py` uses Haar DWT, a block DCT, largest-singular-value quantization with the same quarter/three-quarter phases, and repeated message bits:

https://raw.githubusercontent.com/ShieldMnt/invisible-watermark/main/imwatermark/dwtDctSvd.py

There are substantial implementation differences: that code ordinarily uses a different color channel and scale, applies SVD to a full DCT block, and assigns message bits in sequential block order. Paint uses luminance, step 24, the 3×5 AC packing, the 12×12 repetition tile, fixed framing/checksum, and a twelve-tree acceptance model. Similarity establishes a known algorithm family, **not copied code, common authorship, or a specific licensed implementation**.

Microsoft's publicly released InvisMark implementation uses a learned image encoder and ConvNeXt-based extractor:

https://github.com/microsoft/InvisMark

https://raw.githubusercontent.com/microsoft/InvisMark/main/model.py

That architecture differs materially from the recovered local write path. My earlier post records `com.microsoft.invismark.1` in a manifest from a **cloud** generated image:

https://xusheng.dev/posts/reversing/mspaint_invisible_watermark/main/

The defensible conclusion is a customized classical DWT–DCT–SVD/QIM implementation in the local DLL. Whether Microsoft internally brands this local algorithm as an InvisMark variant, and whether its customization is wholly in-house, remains unresolved. The published neural InvisMark robustness numbers should not be attached to this DLL.

## Reproduction

From this directory:

```sh
python3 -m pip install -r requirements.txt
python3 scripts/verify.py
python3 scripts/experiments.py
python3 scripts/watermark.py decode artifacts/texture.native.png
python3 scripts/watermark.py encode artifacts/texture.png --payload 000102030405060708090a0b0c0d0e0f --output artifacts/example.png
python3 scripts/watermark.py erase artifacts/texture.native.png --output artifacts/example-erased.png
```

The payload argument is raw byte order, not a promise about how Windows GUID structures are displayed as text. The checked-in fixtures let the Python checks run without Windows or a Microsoft DLL. See [native reproduction](docs/native-reproduction.md) to rerun the native embedding and overwrite experiments with your own exact-build DLL. No Microsoft DLL, complete decompiler dump, raw stack capture, or account credentials are included.

The original experiment environment used NumPy 2.5.1 and Pillow 12.3.0 on macOS ARM64. Different SVD/BLAS implementations may change nearly degenerate blocks; JPEG and resampling measurements also depend on library versions. The recorded JSON files are historical results; rerunning experiments updates those files in the checkout.

These are two controlled fixtures and two controlled payloads, not an estimate of performance across real-world AI images. The decoder is an independently implemented experimental decoder, without Microsoft's private detector or synchronization logic.

The verification script passes native payload decoding, native payload replacement decoding, Python round trips, exact noise reproduction, and capacity rejection checks. JSON evidence is in `artifacts/validation.json`, `artifacts/experiment_results.json`, and `artifacts/native_overwrite_results.json`. Saved native and modified PNGs permit image comparisons independently of this report.


## Authorship and licensing

Research by [Xusheng Li](https://xusheng.dev/), with AI-assisted reverse engineering and implementation. This repository documents a local follow-up to the original blog post. It is not affiliated with Microsoft.

Original research code and documentation are MIT licensed. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for fixture provenance and exclusions. Extracted model constants are supplied as research evidence, without a claim of ownership over Microsoft's underlying material.
