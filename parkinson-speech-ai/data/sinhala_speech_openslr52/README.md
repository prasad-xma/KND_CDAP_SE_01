# OpenSLR-52: Large Sinhala ASR training data set (Google)

Source: [OpenSLR-52](https://www.openslr.org/52/), a crowdsourced Sinhala
speech corpus collected by Google in Sri Lanka. License: CC BY-SA 4.0.

Only **one of 16 shards** was downloaded (`asr_sinhala_0.zip`, ~915MB) -
the full corpus is ~14.6GB across all shards, far more than this project
needs. This one shard alone covers 477 of the dataset's 478 total speakers
(near-complete speaker coverage), with 11,550 recordings total.

`raw/` (gitignored) is the extracted contents:
- `raw/asr_sinhala/data/<prefix>/*.flac` - the audio files
- `raw/asr_sinhala/utt_spk_text.tsv` - tab-separated `utterance_id  speaker_id  sinhala_text` for the full corpus (not just this shard's utterances)
- `raw/asr_sinhala/LICENSE` - CC BY-SA 4.0 text

**This is NOT a clinical dataset.** Speakers are ordinary crowdsourced
volunteers, not screened for voice or health conditions, and there are no
PD/HC labels of any kind. It cannot be used to train or validate a
Parkinson's classifier. It exists in this project for two narrower,
legitimate purposes only:

1. **Validating `component2_phonation/vowel_segmentation.py` on real Sinhala
   speech.** That module was previously only tested against the Italian PVS
   "pa-ta-ka" DDK recordings (see its module docstring) - this dataset lets
   it be checked against actual Sinhala phonetics (vowel length contrasts,
   different consonant inventory, etc.) before trusting it on real
   participant recordings.
2. **A rough healthy-voice baseline.** Running `extract_phonation_features`
   across a sample of these recordings gives a plausible range for what
   "normal" jitter/shimmer/HNR/F0 look like for Sinhala speakers - useful
   context when interpreting a participant's results, not a substitute for
   an actual control group.

**Still needed, and not solved by this dataset:** a real Sinhala
PD-vs-healthy-control voice dataset. None exists publicly (confirmed via
search, no indexed Sinhala PD voice corpus found anywhere) - this remains
Phase 2 work (ethics-cleared clinical recording), per the project's own
proposal.
