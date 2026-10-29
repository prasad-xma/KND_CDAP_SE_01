// Component 1 - one tap-to-record take with a 5 -> 0 countdown.
//
// Shared by the Live Mic Test screen (live_gate_check_screen.dart) and the
// 2-step test screen (guided_test_screen.dart), so the recording, countdown and
// stop logic exist once.

import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart' show ValueChanged, VoidCallback, kIsWeb;
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

/// Countdown shown to the user: 5 -> 0.
const int takeSeconds = 5;

/// Recording actually stops at 4.8 s: the browser stops the mic a little late,
/// and a real take that ran 5.08 s was rejected as too long (gate maximum: 5 s).
const int takeStopAtMs = 4800;

/// A problem the user should see ("Microphone permission is required ...").
class TakeRecorderException implements Exception {
  final String message;
  const TakeRecorderException(this.message);

  @override
  String toString() => message;
}

/// A finished take: a file path on mobile/desktop, or the WAV bytes on web.
class RecordedTake {
  final String? filePath;
  final List<int>? bytes;

  const RecordedTake({this.filePath, this.bytes});
}

class TakeRecorder {
  final AudioRecorder _recorder = AudioRecorder();
  Timer? _timer;
  bool _recording = false;

  /// Starts recording [name].wav and the countdown. [onTick] gets the seconds
  /// left (5..0) whenever it changes; [onTimeUp] fires once at [takeStopAtMs],
  /// and the caller then calls [stop]. Throws [TakeRecorderException].
  Future<void> start({
    required String name,
    required ValueChanged<int> onTick,
    required VoidCallback onTimeUp,
  }) async {
    if (!kIsWeb && !(await Permission.microphone.request()).isGranted) {
      throw const TakeRecorderException('Microphone permission is required to record.');
    }
    if (!await _recorder.hasPermission()) {
      throw const TakeRecorderException('Microphone permission is required to record.');
    }

    final String path = kIsWeb
        ? '$name.wav'
        : '${(await getTemporaryDirectory()).path}/${name}_${DateTime.now().millisecondsSinceEpoch}.wav';
    try {
      await _recorder.start(
        // streamBufferSize 8192 (max): the browser hands audio to the app ~5x/s
        // instead of ~21x/s, so the countdown keeps drawing smoothly while recording.
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 44100,
          numChannels: 1,
          streamBufferSize: 8192,
        ),
        path: path,
      );
    } catch (e) {
      throw TakeRecorderException('Could not start the microphone. Please try again. ($e)');
    }

    _recording = true;
    final DateTime startedAt = DateTime.now();
    int lastShown = takeSeconds;
    onTick(takeSeconds);

    // Countdown from the real elapsed time (not by counting ticks), so it
    // still stops on time if the browser delays a timer tick.
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(milliseconds: 200), (timer) {
      if (!_recording) {
        timer.cancel();
        return;
      }
      final int elapsedMs = DateTime.now().difference(startedAt).inMilliseconds;
      final int raw = takeSeconds - elapsedMs ~/ 1000;
      final int left = raw < 0 ? 0 : raw;
      if (left != lastShown) {
        lastShown = left;
        onTick(left);
      }
      if (elapsedMs >= takeStopAtMs) {
        timer.cancel();
        onTimeUp();
      }
    });
  }

  /// Live input level in dBFS (about -160 when silent, 0 at full scale), every 100 ms.
  Stream<double> levels() =>
      _recorder.onAmplitudeChanged(const Duration(milliseconds: 100)).map((a) => a.current);

  /// Stops recording and returns the take. Throws [TakeRecorderException] if
  /// nothing usable was captured.
  Future<RecordedTake> stop() async {
    _timer?.cancel();
    _timer = null;
    if (!_recording) throw const TakeRecorderException('Not recording.');
    _recording = false;

    String? path;
    try {
      path = await _recorder.stop().timeout(const Duration(seconds: 5));
    } catch (_) {
      try {
        await _recorder.cancel();
      } catch (_) {}
      throw const TakeRecorderException('The recording could not be stopped properly. Please record again.');
    }
    if (path == null) throw const TakeRecorderException('Recording failed. Please try again.');
    if (!kIsWeb) return RecordedTake(filePath: path);

    final List<int> bytes = (await http.get(Uri.parse(path))).bodyBytes;
    if (bytes.length < 1000) {
      throw const TakeRecorderException('No audio was captured. Check the microphone and try again.');
    }
    return RecordedTake(bytes: bytes);
  }

  /// Deletes a take's temporary file (nothing to do on web).
  static Future<void> deleteFile(String? path) async {
    if (kIsWeb || path == null) return;
    final file = File(path);
    if (await file.exists()) await file.delete();
  }

  void dispose() {
    _timer?.cancel();
    _recording = false;
    _recorder.dispose();
  }
}
