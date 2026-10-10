import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/phonation_result.dart';

/// Talks to Component 2's standalone FastAPI server
/// (parkinson-speech-ai/component2_phonation/api.py).
///
/// EDIT [baseUrl] below to match how you're running the app:
///   - Chrome (web)      -> http://127.0.0.1:8000          (current default)
///   - Windows desktop   -> http://127.0.0.1:8000
///   - Android emulator  -> http://10.0.2.2:8000          (emulator's alias for the host machine)
///   - iOS simulator     -> http://127.0.0.1:8000          (simulator shares the host's network)
///   - Physical phone    -> http://<your-laptop-LAN-IP>:8000  (e.g. http://192.168.1.23:8000 - find
///                          it with `ipconfig` on Windows; phone and laptop must be on the same wifi)
class PhonationApiService {
  static const String baseUrl = 'http://127.0.0.1:8000';

  /// Uploads a recording (native platforms - real file on disk) and returns
  /// the PD/HC prediction. Throws an [Exception] with a readable message on
  /// any failure.
  ///
  /// [extractVowelSegment]: false measures the whole recording as-is; true
  /// crops out the longest vowel-like segment first and measures only that
  /// (see api.py's screen_phonation docstring - this exists to compare the
  /// two approaches head to head on phrase recordings).
  static Future<PhonationResult> screenVowelRecording(
    String filePath, {
    bool extractVowelSegment = false,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/phonation/screen'))
      ..fields['extract_vowel_segment'] = extractVowelSegment.toString()
      ..files.add(await http.MultipartFile.fromPath('audio', filePath));
    return _sendAndParse(request);
  }

  /// Same as [screenVowelRecording] but from raw bytes (web - recordings
  /// live in browser memory/a blob, not on a real filesystem).
  static Future<PhonationResult> screenVowelRecordingBytes(
    List<int> bytes, {
    String filename = 'recording.wav',
    bool extractVowelSegment = false,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/phonation/screen'))
      ..fields['extract_vowel_segment'] = extractVowelSegment.toString()
      ..files.add(http.MultipartFile.fromBytes('audio', bytes, filename: filename));
    return _sendAndParse(request);
  }

  static Future<PhonationResult> _sendAndParse(http.MultipartRequest request) async {
    final json = await _send(request);
    return PhonationResult.fromJson(json);
  }

  static Future<Map<String, dynamic>> _send(http.MultipartRequest request) async {
    final http.StreamedResponse streamed;
    try {
      streamed = await request.send().timeout(const Duration(seconds: 60));
    } on SocketException {
      throw Exception(
        'Could not reach the server at $baseUrl. Is the FastAPI server running '
        '(uvicorn component2_phonation.api:app --host 0.0.0.0 --port 8000), and is '
        'baseUrl in phonation_api_service.dart set correctly for how you\'re running the app?',
      );
    } on http.ClientException catch (e) {
      throw Exception(
        'Could not reach the server at $baseUrl ($e). If running in Chrome, check the '
        'server is up and that baseUrl matches (http://127.0.0.1:8000 for a local server).',
      );
    }

    final response = await http.Response.fromStream(streamed);

    if (response.statusCode != 200) {
      throw Exception('Server error (${response.statusCode}): ${response.body}');
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }
}
