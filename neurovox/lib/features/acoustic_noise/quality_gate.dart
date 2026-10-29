// Component 1 - the one call other screens make before sending audio on.
//
//   final report = await QualityGate.check(task: QualityTask.vowel, filePath: path);
//
// Returns the report on PASS. Throws [QualityGateRejected] on FAIL, whose
// toString() is the message to show the user, so the caller only needs to
// ask for a new recording.

import 'models/quality_report.dart';
import 'services/quality_gate_api_service.dart';

export 'models/quality_report.dart';

class QualityGate {
  QualityGate._();

  /// Master switch. Set to false to bypass the gate (e.g. a teammate testing
  /// their own component without the port-8001 server running).
  static bool enabled = true;

  /// Gates one recording. Pass [filePath] on mobile/desktop or [bytes] on web.
  /// Returns null when the gate is disabled.
  static Future<QualityReport?> check({
    required QualityTask task,
    String? filePath,
    List<int>? bytes,
    String filename = 'recording.wav',
  }) async {
    if (!enabled) return null;
    final report =
        await QualityGateApiService.check(task: task, filePath: filePath, bytes: bytes, filename: filename);
    if (!report.passed) throw QualityGateRejected(report);
    return report;
  }
}
