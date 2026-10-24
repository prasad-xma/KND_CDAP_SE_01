import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/phonation_result.dart';

class PhonationApiService {
  static const String baseUrl = 'http://127.0.0.1:8000';

  static Future<PhonationResult> screenVowelRecording(
    String filePath, {
    bool extractVowelSegment = false,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/phonation/screen'))
      ..fields['extract_vowel_segment'] = extractVowelSegment.toString()
      ..files.add(await http.MultipartFile.fromPath('audio', filePath));
    return _sendAndParse(request);
  }

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

  static Future<PhonationDualResult> screenDualRecording({
    required String vowelFilePath,
    required String phraseFilePath,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/phonation/screen_dual'))
      ..files.add(await http.MultipartFile.fromPath('vowel_audio', vowelFilePath))
      ..files.add(await http.MultipartFile.fromPath('phrase_audio', phraseFilePath));
    return _sendAndParseDual(request);
  }

  static Future<PhonationDualResult> screenDualRecordingBytes({
    required List<int> vowelBytes,
    required List<int> phraseBytes,
    String vowelFilename = 'vowel_recording.wav',
    String phraseFilename = 'phrase_recording.wav',
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/phonation/screen_dual'))
      ..files.add(http.MultipartFile.fromBytes('vowel_audio', vowelBytes, filename: vowelFilename))
      ..files.add(http.MultipartFile.fromBytes('phrase_audio', phraseBytes, filename: phraseFilename));
    return _sendAndParseDual(request);
  }

  static Future<PhonationResult> _sendAndParse(http.MultipartRequest request) async {
    final json = await _send(request);
    return PhonationResult.fromJson(json);
  }

  static Future<PhonationDualResult> _sendAndParseDual(http.MultipartRequest request) async {
    final json = await _send(request);
    return PhonationDualResult.fromJson(json);
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
