# Reverse engineering evidence map

Addresses below are preferred virtual addresses for the exact DLL SHA-256 in `artifacts/target.json`, with image base `0x180000000`. Subtract the image base for RVAs; add the actual loaded base when using ASLR. All dynamic tests kept ASLR enabled.

| Address | Recovered role |
| --- | --- |
| `0x180004750` | Exported `WmkWriteWatermark`; validation, framing, block processing, placement counters, reconstruction |
| `0x180005b18` | Format-1 input conversion from ARGB bytes to luminance/chroma planes |
| `0x180006088` | RGB reconstruction, clipping and truncation |
| `0x1800062d0` | MSB-first message-bit expansion |
| `0x180006438` | Fixed 12×12 message-index tile |
| `0x180006a18` | Haar decomposition |
| `0x180006bd8` | Forward 4×4 separable cosine transform |
| `0x180006f78` | Inverse cosine transform |
| `0x180001100` | DCT cosine-table initialization |
| `0x1800011a0` | Decision-tree vector initialization |
| `0x180128880` | Runtime-initialized 16-double DCT table |
| `0x180128900` | First tree's five vector objects; twelve objects of 120 bytes each |

The original run combined Binary Ninja static analysis with direct P/Invoke calls in native ARM64 PowerShell. The installed DLL was not modified. Temporary debugger instrumentation and raw stack captures are omitted from the public package.

The historical `native_*_status` maps in `target.json` transcribe the recorded harness return values. The pixel captures and their hashes provide independently checkable evidence for decoder interoperability and overwrite behavior. They are not signed attestations from Microsoft.

The Python reconstruction uses NumPy SVD and is not a universally bit-identical substitute for the DLL's numerical routines. The matrix layout, quantization step, message mapping, model vectors, and counter policy are supported by both the static implementation and controlled native output. No claim is made about the decision-tree training objective, Microsoft's unpublished detector, or other product builds.
