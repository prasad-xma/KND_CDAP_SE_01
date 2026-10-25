# DNSMOS P.835 model (used by Component 1 gate comp1-C)

`sig_bak_ovr.onnx` is Microsoft's DNSMOS P.835 non-intrusive speech-quality
model, copied unmodified from the DNS-Challenge repository:
https://github.com/microsoft/DNS-Challenge/tree/master/DNSMOS/DNSMOS

It predicts three 1-5 mean-opinion scores without a clean reference:
SIG (speech quality), BAK (background-noise intrusiveness), OVRL (overall).

Licence: Creative Commons Attribution 4.0 International (CC BY 4.0),
https://github.com/microsoft/DNS-Challenge/blob/master/LICENSE

Citation: C. K. A. Reddy, V. Gopal, R. Cutler, "DNSMOS P.835: A Non-Intrusive
Perceptual Objective Speech Quality Metric to Evaluate Noise Suppressors",
ICASSP 2022.

Requires `onnxruntime` (pip). If it or this file is missing, comp1-C is
skipped and comp1-A / comp1-B still work.
