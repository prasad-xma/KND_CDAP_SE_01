import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/ddk_result.dart';

class DdkApiService {
  static const String baseUrl = 'http://127.0.0.1:8001';

  static Future<DdkResult> screenDualRecording({
    required String paFilePath,
    required String taFilePath,
  }) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/ddk/screen_dual'),
    )
      ..files.add(await http.MultipartFile.fromPath('pa_audio', paFilePath))
      ..files.add(await http.MultipartFile.fromPath('ta_audio', taFilePath));

    try {
      final streamed = await request.send().timeout(const Duration(seconds: 60));
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode != 200) {
        throw Exception('DDK server error (${response.statusCode}): ${response.body}');
      }
      return DdkResult.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    } on SocketException {
      throw Exception(
        'Could not reach the Component 3 server at $baseUrl. '
        'Start uvicorn component3_ddk.api:app on port 8001.',
      );
    } on http.ClientException catch (error) {
      throw Exception('Could not reach the Component 3 server: $error');
    }
  }
}
