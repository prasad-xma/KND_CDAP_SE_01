// Component 1 - Acoustic Robustness & Noise Handling (quality gate).
//
// The parts of the Component 1 server's report.json that the app uses:
//   POST /quality/check  (parkinson-speech-ai/component1_robustness/api.py)
// The full report (quality metrics, features, voice check) stays on the server,
// saved in outputs/component1/<clip_id>/report.json.

/// The speaking task a recording belongs to. The gate checks that enhancement
/// preserves the biomarkers of the component that will receive the audio:
/// vowel -> Component 2 (phonation), ddk -> Component 3 (speech-motor).
enum QualityTask {
  vowel('vowel'),
  ddk('ddk');

  final String apiValue;
  const QualityTask(this.apiValue);
}

class QualityReport {
  static const String pass = 'PASS';
  static const String fail = 'FAIL';

  /// 'PASS' or 'FAIL'.
  final String decision;

  /// Machine-readable reason, e.g. 'ok', 'too_short', 'low_snr', 'no_voice'.
  final String reason;

  /// 0-100, higher is better.
  final double qualityScore;

  /// 'enhanced' or 'raw' on PASS, null on FAIL.
  final String? audioChoice;

  /// Ready-to-show instruction for the user ("Please record again in a quieter room").
  final String userMessage;

  const QualityReport({
    required this.decision,
    required this.reason,
    required this.qualityScore,
    this.audioChoice,
    required this.userMessage,
  });

  factory QualityReport.fromJson(Map<String, dynamic> json) {
    return QualityReport(
      decision: json['decision'] as String? ?? fail,
      reason: json['reason'] as String? ?? '',
      qualityScore: (json['quality_score'] as num?)?.toDouble() ?? 0.0,
      audioChoice: json['audio_choice'] as String?,
      userMessage: json['user_message'] as String? ?? 'Please record again.',
    );
  }

  bool get passed => decision == pass;
}

/// Thrown when the gate rejects a recording. [toString] is the user-facing
/// message, so existing `catch (e) { _recordError = e.toString(); }` code shows
/// the right text without changes.
class QualityGateRejected implements Exception {
  final QualityReport report;
  const QualityGateRejected(this.report);

  @override
  String toString() => report.userMessage;
}
