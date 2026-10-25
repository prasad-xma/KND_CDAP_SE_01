class PhonationResult {
  final String prediction;
  final double probabilityPd;
  final double probabilityHc;
  final Map<String, double> features;

  final bool extractionUsed;
  final double? segmentStartSeconds;
  final double? segmentEndSeconds;
  final double? segmentDurationSeconds;

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

class PhonationDualResult {
  final String prediction;
  final double probabilityPd;
  final double probabilityHc;
  final PhonationResult vowelTask;
  final PhonationResult phraseTask;

  const PhonationDualResult({
    required this.prediction,
    required this.probabilityPd,
    required this.probabilityHc,
    required this.vowelTask,
    required this.phraseTask,
  });

  factory PhonationDualResult.fromJson(Map<String, dynamic> json) {
    return PhonationDualResult(
      prediction: json['prediction'] as String,
      probabilityPd: (json['probability_pd'] as num).toDouble(),
      probabilityHc: (json['probability_hc'] as num).toDouble(),
      vowelTask: PhonationResult.fromJson(json['vowel_task'] as Map<String, dynamic>),
      phraseTask: PhonationResult.fromJson(json['phrase_task'] as Map<String, dynamic>),
    );
  }

  bool get isPd => prediction == 'PD';
}
