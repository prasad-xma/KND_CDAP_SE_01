// Component 1 - HTTP client for the audio quality gate server.
//
// Start the server from parkinson-speech-ai/:
//   uvicorn component1_robustness.api:app --reload --host 0.0.0.0 --port 8001
//
// Same pattern as core/services/phonation_api_service.dart (Component 2),
// but on port 8001 so both servers can run side by side.

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/quality_report.dart';

/// The gate server could not be reached or answered with an error.
/// [toString] is the message to show.
class GateServerException implements Exception {
  final String message;
  const GateServerException(this.message);

  @override
  String toString() => message;
}

class QualityGateApiService {
  /// Laptop address, shared with PhonationApiService. Default 127.0.0.1 works
  /// for Chrome / desktop. Phone: `flutter run --dart-define=API_HOST=<laptop-wifi-ip>`.
  /// Android emulator: `--dart-define=API_HOST=10.0.2.2`.
  static const String _host = String.fromEnvironment('API_HOST', defaultValue: '127.0.0.1');
  static const String baseUrl = 'http://$_host:8001';

  static const Duration _timeout = Duration(seconds: 60);

  /// Checks one take: [bytes] on Flutter web (where `record` gives a blob URL),
  /// [filePath] on Android / iOS / desktop. Returns the report for PASS and FAIL
  /// alike; throws [QualityGateRejected] only if the audio could not be decoded.
  static Future<QualityReport> check({
    required QualityTask task,
    String? filePath,
    List<int>? bytes,
    String filename = 'recording.wav',
  }) async {
    assert(filePath != null || bytes != null, 'Give either filePath or bytes');
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/quality/check'))
      ..fields['task'] = task.apiValue
      ..files.add(bytes != null
          ? http.MultipartFile.fromBytes('audio', bytes, filename: filename)
          : await http.MultipartFile.fromPath('audio', filePath!));
    final response = await _reach(() async => http.Response.fromStream(await request.send().timeout(_timeout)));

    // A rejected recording is NOT an HTTP error: the server returns 200 with
    // decision FAIL. 422 means the audio could not be decoded at all, which
    // to the user is the same thing: record again.
    if (response.statusCode == 422) {
      throw QualityGateRejected(QualityReport.fromJson(const {
        'decision': QualityReport.fail,
        'reason': 'unreadable_audio',
        'user_message': 'The recording could not be read. Please record again.',
      }));
    }
    return QualityReport.fromJson(_json(response));
  }

  /// The gate's thresholds and settings (GET /health), for showing next to measured values.
  static Future<GateThresholds> fetchThresholds() async {
    final response = await _reach(
        () => http.get(Uri.parse('$baseUrl/health')).timeout(const Duration(seconds: 5)));
    return GateThresholds.fromHealthJson(_json(response));
  }

  /// URL of a plot the gate saved for a checked clip: 'waveform.png' or 'spectrogram.png'.
  static String plotUrl(String clipId, String name) => '$baseUrl/quality/plots/$clipId/$name';

  /// Runs one request, turning "server not running / not reachable" into a clear message.
  static Future<http.Response> _reach(Future<http.Response> Function() call) async {
    try {
      return await call();
    } on SocketException {
      throw GateServerException(_unreachableMessage());
    } on TimeoutException {
      throw GateServerException(_unreachableMessage());
    } on http.ClientException catch (e) {
      throw GateServerException('${_unreachableMessage()} ($e)');
    }
  }

  static Map<String, dynamic> _json(http.Response response) {
    if (response.statusCode != 200) {
      throw GateServerException('Quality gate error (${response.statusCode}): ${response.body}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  static String _unreachableMessage() =>
      'Could not reach the quality gate server at $baseUrl. Is it running '
      '(uvicorn component1_robustness.api:app --host 0.0.0.0 --port 8001)? '
      'To skip the gate while developing, set QualityGate.enabled = false in '
      'features/acoustic_noise/quality_gate.dart.';
}
