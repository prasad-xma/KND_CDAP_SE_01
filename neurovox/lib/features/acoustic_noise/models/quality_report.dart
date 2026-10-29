// Component 1 - Acoustic Robustness & Noise Handling (quality gate).
//
// Mirrors the report.json returned by the Component 1 server
//   POST /quality/check  (parkinson-speech-ai/component1_robustness/api.py)
// and the thresholds returned by GET /health. The Live Mic Test screen shows
// all of it; other screens only need decision, score and userMessage.

/// The speaking task a recording belongs to. The gate checks that enhancement
/// preserves the biomarkers of the component that will receive the audio:
/// vowel -> Component 2 (phonation), ddk -> Component 3 (speech-motor).
enum QualityTask {
  vowel('vowel'),
  ddk('ddk');

  final String apiValue;
  const QualityTask(this.apiValue);
}

double? _num(dynamic value) => value is num ? value.toDouble() : null;

Map<String, double?> _numMap(dynamic value) => value is Map
    ? {for (final entry in value.entries) entry.key.toString(): _num(entry.value)}
    : const {};

/// Quality measured on one version of the clip (raw = before, enhanced = after).
class GateMeasures {
  final double? levelDbfs;
  final double? clippingPct;
  final double? voiceActivityPct;
  final double? speechBandContrastDb;

  const GateMeasures({this.levelDbfs, this.clippingPct, this.voiceActivityPct, this.speechBandContrastDb});

  static GateMeasures? fromJson(dynamic json) {
    if (json is! Map) return null;
    return GateMeasures(
      levelDbfs: _num(json['level_dbfs']),
      clippingPct: _num(json['clipping_pct']),
      voiceActivityPct: _num(json['voice_activity_pct']),
      speechBandContrastDb: _num(json['speech_band_contrast_db']),
    );
  }
}

/// The voice presence check, run on the raw audio (voice_check.py).
class VoiceCheckResult {
  final double? speechBandContrastDb;
  final double? levelDbfs;
  final bool passed;

  const VoiceCheckResult({this.speechBandContrastDb, this.levelDbfs, required this.passed});

  static VoiceCheckResult? fromJson(dynamic json) {
    if (json is! Map) return null;
    return VoiceCheckResult(
      speechBandContrastDb: _num(json['speech_band_contrast_db']),
      levelDbfs: _num(json['level_dbfs']),
      passed: json['passed'] == true,
    );
  }
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

  // Details shown on the Live Mic Test screen.
  final String clipId;
  final String task;
  final double durationSeconds;

  /// Null when the clip failed the length check (nothing else was measured).
  final GateMeasures? qualityBefore;
  final GateMeasures? qualityAfter;
  final VoiceCheckResult? voiceCheck;

  /// Biomarkers before/after enhancement, and their relative change.
  final Map<String, double?> featuresBefore;
  final Map<String, double?> featuresAfter;
  final Map<String, double?> featureChange;

  /// Whether enhancement kept every biomarker within tolerance (null if not checked).
  final bool? featuresPreserved;

  const QualityReport({
    required this.decision,
    required this.reason,
    required this.qualityScore,
    this.audioChoice,
    required this.userMessage,
    this.clipId = '',
    this.task = '',
    this.durationSeconds = 0.0,
    this.qualityBefore,
    this.qualityAfter,
    this.voiceCheck,
    this.featuresBefore = const {},
    this.featuresAfter = const {},
    this.featureChange = const {},
    this.featuresPreserved,
  });

  factory QualityReport.fromJson(Map<String, dynamic> json) {
    final preservation = json['feature_preserved'];
    return QualityReport(
      decision: json['decision'] as String? ?? fail,
      reason: json['reason'] as String? ?? '',
      qualityScore: _num(json['quality_score']) ?? 0.0,
      audioChoice: json['audio_choice'] as String?,
      userMessage: json['user_message'] as String? ?? 'Please record again.',
      clipId: json['clip_id'] as String? ?? '',
      task: json['task'] as String? ?? '',
      durationSeconds: _num(json['duration_s']) ?? 0.0,
      qualityBefore: GateMeasures.fromJson(json['quality_before']),
      qualityAfter: GateMeasures.fromJson(json['quality_after']),
      voiceCheck: VoiceCheckResult.fromJson(json['voice_check']),
      featuresBefore: _numMap(json['features_before']),
      featuresAfter: _numMap(json['features_after']),
      featureChange: preservation is Map ? _numMap(preservation['per_feature']) : const {},
      featuresPreserved: preservation is Map ? preservation['preserved'] as bool? : null,
    );
  }

  bool get passed => decision == pass;

  /// The quality the gate judged: the enhanced audio if enhancement kept the
  /// biomarkers, otherwise the raw audio (pipeline.py).
  GateMeasures? get judgedQuality => featuresPreserved == true ? qualityAfter : qualityBefore;
}

/// The limits the gate compares against, from GET /health (configs/component1.yaml).
class GateThresholds {
  final double minDurationS;
  final double maxDurationS;
  final double maxClippingPct;
  final double minVoiceActivityPct;
  final double passContrastDb;
  final double minContrastDb;
  final double noVoiceMaxLevelDbfs;

  /// Relative-change tolerance per biomarker, per task ('vowel' / 'ddk').
  final Map<String, Map<String, double?>> featureTolerances;
  final String gateModel;
  final String enhancementMethod;
  final String configVersion;

  const GateThresholds({
    required this.minDurationS,
    required this.maxDurationS,
    required this.maxClippingPct,
    required this.minVoiceActivityPct,
    required this.passContrastDb,
    required this.minContrastDb,
    required this.noVoiceMaxLevelDbfs,
    required this.featureTolerances,
    required this.gateModel,
    required this.enhancementMethod,
    required this.configVersion,
  });

  factory GateThresholds.fromHealthJson(Map<String, dynamic> json) {
    final t = json['thresholds'] as Map<String, dynamic>? ?? const {};
    final tolerances = t['feature_tolerances'];
    return GateThresholds(
      minDurationS: _num(t['min_duration_s']) ?? 0,
      maxDurationS: _num(t['max_duration_s']) ?? 0,
      maxClippingPct: _num(t['max_clipping_pct']) ?? 0,
      minVoiceActivityPct: _num(t['min_voice_activity_pct']) ?? 0,
      passContrastDb: _num(t['comp1a_pass_db']) ?? 0,
      minContrastDb: _num(t['min_speech_band_contrast_db']) ?? 0,
      noVoiceMaxLevelDbfs: _num(t['no_voice_max_level_dbfs']) ?? 0,
      featureTolerances: tolerances is Map
          ? {for (final entry in tolerances.entries) entry.key.toString(): _numMap(entry.value)}
          : const {},
      gateModel: json['gate_model'] as String? ?? '',
      enhancementMethod: json['enhancement_method'] as String? ?? '',
      configVersion: json['config_version'] as String? ?? '',
    );
  }
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
