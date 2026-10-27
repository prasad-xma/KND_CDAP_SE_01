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
  final PhonationResult? phraseTask;

  const PhonationDualResult({
    required this.prediction,
    required this.probabilityPd,
    required this.probabilityHc,
    required this.vowelTask,
    this.phraseTask,
  });

  factory PhonationDualResult.fromJson(Map<String, dynamic> json) {
    return PhonationDualResult(
      prediction: json['prediction'] as String,
      probabilityPd: (json['probability_pd'] as num).toDouble(),
      probabilityHc: (json['probability_hc'] as num).toDouble(),
      vowelTask: PhonationResult.fromJson(json['vowel_task'] as Map<String, dynamic>),
      phraseTask: json['phrase_task'] != null
          ? PhonationResult.fromJson(json['phrase_task'] as Map<String, dynamic>)
          : null,
    );
  }

  factory PhonationDualResult.vowelOnly(PhonationResult vowelTask) {
    return PhonationDualResult(
      prediction: vowelTask.prediction,
      probabilityPd: vowelTask.probabilityPd,
      probabilityHc: vowelTask.probabilityHc,
      vowelTask: vowelTask,
    );
  }

  bool get isPd => prediction == 'PD';
}

class PhonationMultiResult {
  final String prediction;
  final double probabilityPd;
  final double probabilityHc;
  final List<PhonationResult> recordings;

  const PhonationMultiResult({
    required this.prediction,
    required this.probabilityPd,
    required this.probabilityHc,
    required this.recordings,
  });

  factory PhonationMultiResult.fromJson(Map<String, dynamic> json) {
    return PhonationMultiResult(
      prediction: json['prediction'] as String,
      probabilityPd: (json['probability_pd'] as num).toDouble(),
      probabilityHc: (json['probability_hc'] as num).toDouble(),
      recordings: (json['recordings'] as List)
          .map((r) => PhonationResult.fromJson(r as Map<String, dynamic>))
          .toList(),
    );
  }

  bool get isPd => prediction == 'PD';

  PhonationResult toAveragedResult() {
    final Map<String, double> avgFeatures = {};
    if (recordings.isNotEmpty) {
      for (final key in recordings.first.features.keys) {
        final sum = recordings.fold<double>(0, (acc, r) => acc + (r.features[key] ?? 0));
        avgFeatures[key] = sum / recordings.length;
      }
    }
    return PhonationResult(
      prediction: prediction,
      probabilityPd: probabilityPd,
      probabilityHc: probabilityHc,
      features: avgFeatures,
      extractionUsed: true,
      modelUsed: recordings.isNotEmpty ? recordings.first.modelUsed : 'vowel_combined_tuned',
    );
  }
}
