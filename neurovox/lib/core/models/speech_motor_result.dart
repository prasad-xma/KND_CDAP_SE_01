class SpeechMotorResult {
  final String prediction;
  final double probabilityPd;
  final double probabilityHc;
  final bool isPlaceholder;

  const SpeechMotorResult({
    required this.prediction,
    required this.probabilityPd,
    required this.probabilityHc,
    this.isPlaceholder = false,
  });

  factory SpeechMotorResult.placeholder() {
    return const SpeechMotorResult(
      prediction: 'PD',
      probabilityPd: 0.5,
      probabilityHc: 0.5,
      isPlaceholder: true,
    );
  }

  bool get isPd => prediction == 'PD';
}
