// Component 1 - HTTP client for the audio quality gate server.
//
// Start the server from parkinson-speech-ai/:
//   uvicorn component1_robustness.api:app --reload --host 0.0.0.0 --port 8001
//
// Same pattern as core/services/phonation_api_service.dart (Component 2),
// but on port 8001 so both servers can run side by side.

import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/quality_report.dart';

class QualityGateApiService {
  /// Laptop address, shared with PhonationApiService. Default 127.0.0.1 works
  /// for Chrome / desktop. Phone: `flutter run --dart-define=API_HOST=<laptop-wifi-ip>`.
  /// Android emulator: `--dart-define=API_HOST=10.0.2.2`.
  static const String _host = String.fromEnvironment('API_HOST', defaultValue: '127.0.0.1');
  static const String baseUrl = 'http://$_host:8001';

  static const Duration _timeout = Duration(seconds: 60);

  /// Checks a recording saved on disk (Android / iOS / desktop).
  static Future<QualityReport> checkFile(String filePath, QualityTask task) async {
    final request = _newRequest(task)
      ..files.add(await http.MultipartFile.fromPath('audio', filePath));
    return _send(request);
  }

  /// Checks a recording held in memory (Flutter web, where `record` gives a blob URL).
  static Future<QualityReport> checkBytes(
    List<int> bytes,
    QualityTask task, {
    String filename = 'recording.wav',
  }) async {
    final request = _newRequest(task)
      ..files.add(http.MultipartFile.fromBytes('audio', bytes, filename: filename));
    return _send(request);
  }

  static http.MultipartRequest _newRequest(QualityTask task) {
    return http.MultipartRequest('POST', Uri.parse('$baseUrl/quality/check'))
      ..fields['task'] = task.apiValue;
  }

  static Future<QualityReport> _send(http.MultipartRequest request) async {
    final http.StreamedResponse streamed;
    try {
      streamed = await request.send().timeout(_timeout);
    } on SocketException {
      throw Exception(_unreachableMessage());
    } on http.ClientException catch (e) {
      throw Exception('${_unreachableMessage()} ($e)');
    }

    final response = await http.Response.fromStream(streamed);

    // A rejected recording is NOT an HTTP error: the server returns 200 with
    // decision FAIL. 422 means the audio could not be decoded at all, which
    // to the user is the same thing: record again.
    if (response.statusCode == 422) {
      throw QualityGateRejected(QualityReport.fromJson(const {
        'decision': QualityReport.fail,
        'user_message': 'The recording could not be read. Please record again.',
      }));
    }
    if (response.statusCode != 200) {
      throw Exception('Quality gate error (${response.statusCode}): ${response.body}');
    }
    return QualityReport.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  static String _unreachableMessage() =>
      'Could not reach the quality gate server at $baseUrl. Is it running '
      '(uvicorn component1_robustness.api:app --host 0.0.0.0 --port 8001)? '
      'To skip the gate while developing, set QualityGate.enabled = false in '
      'features/acoustic_noise/quality_gate.dart.';
}
