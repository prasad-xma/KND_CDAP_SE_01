class DdkRecordingResult {
  final String filename;
  final String task;
  final String predictedClass;
  final double pdProbability;

  const DdkRecordingResult({
    required this.filename,
    required this.task,
    required this.predictedClass,
    required this.pdProbability,
  });

  factory DdkRecordingResult.fromJson(Map<String, dynamic> json) {
    return DdkRecordingResult(
      filename: json['filename'] as String,
      task: json['task'] as String,
      predictedClass: json['predicted_class'] as String,
      pdProbability: (json['pd_probability'] as num).toDouble(),
    );
  }
}

class DdkResult {
  final DdkRecordingResult paResult;
  final DdkRecordingResult taResult;
  final double meanPdProbability;
  final String combinedPrediction;
  final String interpretationNote;

  const DdkResult({
    required this.paResult,
    required this.taResult,
    required this.meanPdProbability,
    required this.combinedPrediction,
    required this.interpretationNote,
  });

  factory DdkResult.fromJson(Map<String, dynamic> json) {
    return DdkResult(
      paResult: DdkRecordingResult.fromJson(json['pa_result'] as Map<String, dynamic>),
      taResult: DdkRecordingResult.fromJson(json['ta_result'] as Map<String, dynamic>),
      meanPdProbability: (json['mean_pd_probability'] as num).toDouble(),
      combinedPrediction: json['combined_prediction'] as String,
      interpretationNote: json['interpretation_note'] as String,
    );
  }
}
