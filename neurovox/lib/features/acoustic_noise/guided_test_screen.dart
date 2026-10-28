// Component 1 - guided 2-step voice test, opened from Home's "Start Test".
//
//   Step 1 of 2  Phonation     "aaaa"      -> quality gate (vowel) -> Component 2
//   Step 2 of 2  Speech-Motor  "pa-ta-ka"  -> quality gate (ddk)   -> Component 3 (coming soon)
//
// Every take goes through the Component 1 gate first. A rejected take shows the
// gate's message and the user re-records the same step. The vowel take is only
// sent to Component 2 after BOTH steps have passed the gate.

import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import '../../core/models/phonation_result.dart';
import '../../core/services/phonation_api_service.dart';
import 'quality_gate.dart';

const Color _bg = Color(0xFF0A0E14);
const Color _surface = Color(0xFF131A24);
const Color _surfaceRaised = Color(0xFF1A2330);
const Color _stroke = Color(0xFF232E3D);
const Color _accent = Color(0xFF22E6C9);
const Color _accentDim = Color(0xFF0C9388);
const Color _warn = Color(0xFFFFB24B);
const Color _danger = Color(0xFFFF6B6B);
const Color _textPrimary = Color(0xFFEFF4F8);
const Color _textSecondary = Color(0xFF8C9AAE);
const Color _textFaint = Color(0xFF5B6778);

class _TestStep {
  final QualityTask task;
  final String title;
  final String instruction;
  final String prompt;
  final int seconds;
  final IconData icon;

  const _TestStep({
    required this.task,
    required this.title,
    required this.instruction,
    required this.prompt,
    required this.seconds,
    required this.icon,
  });
}

/// Each take: countdown 5 -> 0, then recording stops by itself.
/// The gate's maximum is also 5 s (configs/component1.yaml: 1.5-5 s).
const int _recordSeconds = 5;

/// Recording actually stops at 4.8 s: the browser stops the mic a little late, and a
/// real take that ran 5.08 s was rejected as too long. The display still ends at 0.
const int _stopAtMs = 4800;

const List<_TestStep> _steps = [
  _TestStep(
    task: QualityTask.vowel,
    title: 'Phonation',
    instruction: 'Take a breath, then say "aaaa" in one steady sound until the timer ends.',
    prompt: '"aaaaaaaa..."',
    seconds: _recordSeconds,
    icon: Icons.graphic_eq_rounded,
  ),
  _TestStep(
    task: QualityTask.ddk,
    title: 'Speech-Motor',
    instruction: 'Repeat "pa-ta-ka" as quickly and clearly as you can until the timer ends.',
    prompt: '"pa-ta-ka  pa-ta-ka..."',
    seconds: _recordSeconds,
    icon: Icons.record_voice_over_rounded,
  ),
];

enum _Phase { ready, recording, checking, rejected, analysing, done }

class GuidedTestScreen extends StatefulWidget {
  /// Called with the Component 2 result so Home can show it in Reports.
  final ValueChanged<PhonationDualResult>? onPhonationResult;

  const GuidedTestScreen({super.key, this.onPhonationResult});

  @override
  State<GuidedTestScreen> createState() => _GuidedTestScreenState();
}

class _GuidedTestScreenState extends State<GuidedTestScreen> {
  final AudioRecorder _recorder = AudioRecorder();
  Timer? _timer;

  int _stepIndex = 0;
  _Phase _phase = _Phase.ready;
  int _remaining = 0;
  DateTime? _recordingStartedAt;
  String? _message;

  /// Gate report per step (null = not recorded yet, or gate switched off).
  final List<QualityReport?> _reports = [null, null];
  final List<bool> _stepPassed = [false, false];

  String? _vowelPath;
  List<int>? _vowelBytes;

  PhonationResult? _phonation;
  String? _phonationError;

  _TestStep get _step => _steps[_stepIndex];

  @override
  void dispose() {
    _timer?.cancel();
    _recorder.dispose();
    _deleteFile(_vowelPath);
    super.dispose();
  }

  // --- Recording -------------------------------------------------------------

  Future<String> _newRecordingPath(QualityTask task) async {
    if (kIsWeb) return '${task.apiValue}_take.wav';
    final dir = await getTemporaryDirectory();
    return '${dir.path}/${task.apiValue}_take_${DateTime.now().millisecondsSinceEpoch}.wav';
  }

  Future<void> _deleteFile(String? path) async {
    if (kIsWeb || path == null) return;
    final f = File(path);
    if (await f.exists()) await f.delete();
  }

  Future<void> _startRecording() async {
    if (!kIsWeb) {
      final status = await Permission.microphone.request();
      if (!status.isGranted) {
        _showProblem('Microphone permission is required to run this test.');
        return;
      }
    }
    if (!await _recorder.hasPermission()) {
      _showProblem('Microphone permission is required to run this test.');
      return;
    }

    final path = await _newRecordingPath(_step.task);
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
      _showProblem('Could not start the microphone. Please try again. ($e)');
      return;
    }
    if (!mounted) return;

    final int seconds = _step.seconds;
    _recordingStartedAt = DateTime.now();
    setState(() {
      _phase = _Phase.recording;
      _remaining = seconds;
      _message = null;
    });

    // Countdown from the real elapsed time (not by counting ticks), so it
    // still stops on time if the browser delays a timer tick.
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(milliseconds: 200), (timer) {
      if (!mounted || _phase != _Phase.recording) {
        timer.cancel();
        return;
      }
      final int elapsedMs = DateTime.now().difference(_recordingStartedAt!).inMilliseconds;
      final int raw = seconds - elapsedMs ~/ 1000;
      final int left = raw < 0 ? 0 : raw;
      if (left != _remaining) setState(() => _remaining = left);
      if (elapsedMs >= _stopAtMs) {
        timer.cancel();
        _stopAndCheck(); // switches the status to "0 · Checking recording quality..."
      }
    });
  }

  Future<void> _stopAndCheck() async {
    // Runs once per take, whether the countdown reached 0 or the user tapped stop.
    if (_phase != _Phase.recording) return;
    _timer?.cancel();
    _timer = null;
    setState(() => _phase = _Phase.checking);

    String? path;
    try {
      path = await _recorder.stop().timeout(const Duration(seconds: 5));
    } catch (e) {
      try {
        await _recorder.cancel();
      } catch (_) {}
      _showProblem('The recording could not be stopped properly. Please record again.');
      return;
    }
    if (!mounted) return;
    if (path == null) {
      _showProblem('Recording failed. Please try again.');
      return;
    }
    final step = _step;
    String? filePath;
    List<int>? bytes;

    try {
      if (kIsWeb) {
        bytes = (await http.get(Uri.parse(path))).bodyBytes;
        if (bytes.length < 1000) {
          throw Exception('No audio was captured. Check the microphone and try again.');
        }
      } else {
        filePath = path;
      }

      final report = await QualityGate.check(
        task: step.task,
        filePath: filePath,
        bytes: bytes,
        filename: '${step.task.apiValue}_take.wav',
      );
      if (!mounted) return;

      _reports[_stepIndex] = report;
      _stepPassed[_stepIndex] = true;

      if (step.task == QualityTask.vowel) {
        _vowelPath = filePath;
        _vowelBytes = bytes;
      } else {
        // Component 3 has no API yet, so the DDK take is not kept.
        await _deleteFile(filePath);
      }

      if (_stepIndex == 0) {
        setState(() {
          _stepIndex = 1;
          _phase = _Phase.ready;
        });
      } else {
        await _analysePhonation();
      }
    } on QualityGateRejected catch (e) {
      await _deleteFile(filePath);
      _showProblem(e.report.userMessage);
    } catch (e) {
      await _deleteFile(filePath);
      _showProblem(e.toString().replaceFirst('Exception: ', ''));
    }
  }

  void _showProblem(String message) {
    if (!mounted) return;
    setState(() {
      _phase = _Phase.rejected;
      _message = message;
    });
  }

  // --- Component 2 -----------------------------------------------------------

  Future<void> _analysePhonation() async {
    setState(() => _phase = _Phase.analysing);
    try {
      final PhonationResult result = kIsWeb
          ? await PhonationApiService.screenVowelRecordingBytes(_vowelBytes!, filename: 'vowel.wav')
          : await PhonationApiService.screenVowelRecording(_vowelPath!);
      if (!mounted) return;
      widget.onPhonationResult?.call(PhonationDualResult.vowelOnly(result));
      setState(() {
        _phonation = result;
        _phase = _Phase.done;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _phonationError = e.toString().replaceFirst('Exception: ', '');
        _phase = _Phase.done;
      });
    } finally {
      await _deleteFile(_vowelPath);
      _vowelPath = null;
      _vowelBytes = null;
    }
  }

  void _restart() {
    setState(() {
      _stepIndex = 0;
      _phase = _Phase.ready;
      _message = null;
      _reports[0] = null;
      _reports[1] = null;
      _stepPassed[0] = false;
      _stepPassed[1] = false;
      _phonation = null;
      _phonationError = null;
    });
  }

  void _onMicTap() {
    switch (_phase) {
      case _Phase.ready:
      case _Phase.rejected:
        _startRecording();
        break;
      case _Phase.recording:
        _stopAndCheck();
        break;
      case _Phase.checking:
      case _Phase.analysing:
      case _Phase.done:
        break;
    }
  }

  // --- UI --------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: _textPrimary,
        title: const Text(
          'Voice Screening Test',
          style: TextStyle(fontWeight: FontWeight.w700, color: _textPrimary, fontSize: 18),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
          child: _phase == _Phase.done ? _buildResults() : _buildStep(),
        ),
      ),
    );
  }

  Widget _buildStepIndicator() {
    return Row(
      children: List.generate(_steps.length, (i) {
        final bool active = i == _stepIndex;
        final bool passed = _stepPassed[i];
        return Expanded(
          child: Container(
            margin: EdgeInsets.only(right: i == _steps.length - 1 ? 0 : 8),
            height: 6,
            decoration: BoxDecoration(
              color: passed ? _accent : (active ? _accent.withValues(alpha: 0.45) : _stroke),
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        );
      }),
    );
  }

  Widget _buildStep() {
    final step = _step;
    final bool busy = _phase == _Phase.checking || _phase == _Phase.analysing;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        _buildStepIndicator(),
        const SizedBox(height: 18),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: _accent.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            'STEP ${_stepIndex + 1} OF ${_steps.length}  ·  ${step.title.toUpperCase()}',
            style: const TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w800,
              color: _accent,
              letterSpacing: 0.5,
            ),
          ),
        ),
        const SizedBox(height: 20),
        if (_stepIndex == 1 && _stepPassed[0]) ...[
          _buildPassedChip('Step 1 passed the quality check', _reports[0]),
          const SizedBox(height: 16),
        ],
        Text(
          step.instruction,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 15, color: _textSecondary, height: 1.45),
        ),
        const SizedBox(height: 14),
        Text(
          step.prompt,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: _textPrimary),
        ),
        const SizedBox(height: 32),
        _buildStatus(),
        const SizedBox(height: 28),
        GestureDetector(
          onTap: busy ? null : _onMicTap,
          child: Container(
            width: 104,
            height: 104,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: _phase == _Phase.recording
                    ? const [Color(0xFFFF8A65), _danger]
                    : busy
                        ? const [_surfaceRaised, _surfaceRaised]
                        : const [_accent, _accentDim],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: busy
                  ? null
                  : [
                      BoxShadow(
                        color: (_phase == _Phase.recording ? _danger : _accent).withValues(alpha: 0.35),
                        blurRadius: 24,
                        offset: const Offset(0, 8),
                      ),
                    ],
            ),
            child: Icon(
              _phase == _Phase.recording ? Icons.stop_rounded : Icons.mic_rounded,
              size: 46,
              color: busy ? _textFaint : const Color(0xFF071210),
            ),
          ),
        ),
        const SizedBox(height: 14),
        Text(
          _micLabel(),
          style: const TextStyle(fontSize: 13, color: _textFaint, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }

  String _micLabel() {
    switch (_phase) {
      case _Phase.ready:
        return 'Tap to record';
      case _Phase.rejected:
        return 'Tap to record again';
      case _Phase.recording:
        return 'Tap to stop early';
      case _Phase.checking:
      case _Phase.analysing:
      case _Phase.done:
        return 'Please wait';
    }
  }

  Widget _buildStatus() {
    switch (_phase) {
      case _Phase.recording:
        return Column(
          children: [
            _countdownNumber('$_remaining', _accent),
            const Text('Listening...', style: TextStyle(color: _accent, fontWeight: FontWeight.w600)),
          ],
        );
      case _Phase.checking:
        // The countdown finished at 0; keep the 0 on screen while the gate checks the take.
        return Column(
          children: [
            _countdownNumber('0', _textFaint),
            _buildBusy('Checking recording quality...'),
          ],
        );
      case _Phase.analysing:
        return _buildBusy('Analysing your voice...');
      case _Phase.rejected:
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: _danger.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: _danger.withValues(alpha: 0.4)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.error_outline_rounded, color: _danger, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  _message ?? 'Please record again.',
                  style: const TextStyle(color: _textPrimary, fontSize: 13.5, height: 1.4),
                ),
              ),
            ],
          ),
        );
      case _Phase.ready:
      case _Phase.done:
        return const SizedBox(
          height: 48,
          child: Center(
            child: Text('Ready when you are', style: TextStyle(color: _textSecondary, fontSize: 14)),
          ),
        );
    }
  }

  Widget _countdownNumber(String text, Color color) {
    return Text(
      text,
      style: TextStyle(
        fontSize: 48,
        fontWeight: FontWeight.w800,
        color: color,
        fontFeatures: const [FontFeature.tabularFigures()],
      ),
    );
  }

  Widget _buildBusy(String label) {
    return SizedBox(
      height: 72,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox(
            width: 26,
            height: 26,
            child: CircularProgressIndicator(strokeWidth: 3, color: _accent),
          ),
          const SizedBox(height: 12),
          Text(label, style: const TextStyle(color: _textSecondary, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _buildPassedChip(String label, QualityReport? report) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: _accent.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _accent.withValues(alpha: 0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.check_circle_rounded, color: _accent, size: 18),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              report == null ? label : '$label (score ${report.qualityScore.toStringAsFixed(0)})',
              style: const TextStyle(color: _textPrimary, fontSize: 12.5, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  // --- Results ---------------------------------------------------------------

  Widget _buildResults() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _buildStepIndicator(),
        const SizedBox(height: 22),
        const Text(
          'Test complete',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: _textPrimary),
        ),
        const SizedBox(height: 6),
        const Text(
          'Both recordings passed the quality check.',
          style: TextStyle(fontSize: 13.5, color: _textSecondary),
        ),
        const SizedBox(height: 20),
        _buildResultCard(
          stepLabel: 'STEP 1 OF 2',
          title: 'Phonation',
          icon: _steps[0].icon,
          report: _reports[0],
          body: _buildPhonationBody(),
        ),
        const SizedBox(height: 14),
        _buildResultCard(
          stepLabel: 'STEP 2 OF 2',
          title: 'Speech-Motor',
          icon: _steps[1].icon,
          report: _reports[1],
          body: const Text(
            'Motor analysis is coming soon (Component 3).',
            style: TextStyle(color: _textSecondary, fontSize: 13.5),
          ),
        ),
        const SizedBox(height: 18),
        const Text(
          'This is a screening aid, not a diagnosis. Please consult a doctor about any concerns.',
          style: TextStyle(color: _textFaint, fontSize: 12, height: 1.4),
        ),
        const SizedBox(height: 22),
        ElevatedButton(
          onPressed: () => Navigator.of(context).maybePop(),
          style: ElevatedButton.styleFrom(
            backgroundColor: _accent,
            foregroundColor: const Color(0xFF071210),
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          ),
          child: const Text('Done', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
        ),
        const SizedBox(height: 10),
        TextButton(
          onPressed: _restart,
          child: const Text('Run the test again', style: TextStyle(color: _accent, fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }

  Widget _buildPhonationBody() {
    if (_phonationError != null) {
      return Text(
        'Could not get the phonation result: $_phonationError',
        style: const TextStyle(color: _warn, fontSize: 13, height: 1.4),
      );
    }
    final r = _phonation;
    if (r == null) return const SizedBox.shrink();
    final bool pd = r.isPd;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          pd ? 'Voice pattern similar to PD' : 'Voice pattern similar to healthy controls',
          style: TextStyle(
            color: pd ? _warn : _accent,
            fontSize: 15,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          'PD probability: ${(r.probabilityPd * 100).toStringAsFixed(0)}%',
          style: const TextStyle(color: _textSecondary, fontSize: 13),
        ),
      ],
    );
  }

  Widget _buildResultCard({
    required String stepLabel,
    required String title,
    required IconData icon,
    required QualityReport? report,
    required Widget body,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _stroke),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: _accent, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(color: _textPrimary, fontSize: 16, fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                stepLabel,
                style: const TextStyle(color: _textFaint, fontSize: 11, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            report == null
                ? 'Quality gate: off'
                : 'Quality gate: PASS · score ${report.qualityScore.toStringAsFixed(0)} · ${report.audioChoice ?? '-'} audio',
            style: const TextStyle(color: _textFaint, fontSize: 12),
          ),
          const SizedBox(height: 10),
          body,
        ],
      ),
    );
  }
}
