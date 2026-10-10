/// Result of calling Component 2's /phonation/screen endpoint.
class PhonationResult {
  final String prediction; // "PD" or "HC"
  final double probabilityPd;
  final double probabilityHc;
  final Map<String, double> features; // mean_f0, jitter, shimmer, hnr, etc. - see features.py

  /// Whether the server cropped a vowel-like segment out of the recording
  /// before measuring it (true), or measured the whole recording as-is
  /// (false) - see api.py's screen_phonation docstring for why this exists.
  final bool extractionUsed;
  final double? segmentStartSeconds;
  final double? segmentEndSeconds;
  final double? segmentDurationSeconds;

  /// Which trained model actually produced this prediction - "readtext"
  /// (~78% CV accuracy, trained on MDVR-KCL English passage recordings) when
  /// extraction was off, or "vowel_combined_tuned" (82.7% CV accuracy) when
  /// extraction was on. The server picks the model that matches what it was
  /// actually fed, so the prediction is meaningful either way.
  final String modelUsed;

  const PhonationResult({
    required this.prediction,
    required this.probabilityPd,
    required this.probabilityHc,
    this.features = const {},
    this.extractionUsed = false,
    this.segmentStartSeconds,
    this.segmentEndSeconds,
    this.segmentDurationSeconds,
    this.modelUsed = 'vowel_combined_tuned',
  });

  factory PhonationResult.fromJson(Map<String, dynamic> json) {
    return PhonationResult(
      prediction: json['prediction'] as String,
      probabilityPd: (json['probability_pd'] as num).toDouble(),
      probabilityHc: (json['probability_hc'] as num).toDouble(),
      features: (json['features'] as Map<String, dynamic>?)
              ?.map((k, v) => MapEntry(k, (v as num).toDouble())) ??
          const {},
      extractionUsed: json['extraction_used'] as bool? ?? false,
      segmentStartSeconds: (json['segment_start_seconds'] as num?)?.toDouble(),
      segmentEndSeconds: (json['segment_end_seconds'] as num?)?.toDouble(),
      segmentDurationSeconds: (json['segment_duration_seconds'] as num?)?.toDouble(),
      modelUsed: json['model_used'] as String? ?? 'vowel_combined_tuned',
    );
  }

  bool get isPd => prediction == 'PD';
}
