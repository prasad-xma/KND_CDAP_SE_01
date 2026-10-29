// Component 1 - guided 2-step voice test (not opened anywhere at the moment).
//
//   Step 1 of 2  Phonation     "aaaa"      -> quality gate (vowel) -> Component 2
//   Step 2 of 2  Speech-Motor  "pa-ta-ka"  -> quality gate (ddk)   -> Component 3 (coming soon)
//
// Every take goes through the Component 1 gate first. A rejected take shows the
// gate's message and the user re-records the same step. The vowel take is only
// sent to Component 2 after BOTH steps have passed the gate.

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import '../../core/models/phonation_result.dart';
import '../../core/services/phonation_api_service.dart';
import 'gate_colors.dart';
import 'quality_gate.dart';
import 'take_recorder.dart';

class _TestStep {
  final QualityTask task;
  final String title;
  final String instruction;
  final String prompt;
  final IconData icon;

  const _TestStep({
    required this.task,
    required this.title,
    required this.instruction,
    required this.prompt,
    required this.icon,
  });
}

const List<_TestStep> _steps = [
  _TestStep(
    task: QualityTask.vowel,
    title: 'Phonation',
    instruction: 'Take a breath, then say "aaaa" in one steady sound until the timer ends.',
    prompt: '"aaaaaaaa..."',
    icon: Icons.graphic_eq_rounded,
  ),
  _TestStep(
    task: QualityTask.ddk,
    title: 'Speech-Motor',
    instruction: 'Repeat "pa-ta-ka" as quickly and clearly as you can until the timer ends.',
    prompt: '"pa-ta-ka  pa-ta-ka..."',
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
  final TakeRecorder _takeRecorder = TakeRecorder();

  int _stepIndex = 0;
  _Phase _phase = _Phase.ready;
  int _remaining = 0;
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
    _takeRecorder.dispose();
    TakeRecorder.deleteFile(_vowelPath);
    super.dispose();
  }

  // --- Recording (shared logic in take_recorder.dart) -------------------------

  Future<void> _startRecording() async {
    try {
      await _takeRecorder.start(
        name: '${_step.task.apiValue}_take',
        onTick: (left) {
          if (mounted) setState(() => _remaining = left);
        },
        onTimeUp: _stopAndCheck, // switches the status to "0 · Checking recording quality..."
      );
    } on TakeRecorderException catch (e) {
      _showProblem(e.message);
      return;
    }
    if (!mounted) return;
    setState(() {
      _phase = _Phase.recording;
      _message = null;
    });
  }

  Future<void> _stopAndCheck() async {
    // Runs once per take, whether the countdown reached 0 or the user tapped stop.
    if (_phase != _Phase.recording) return;
    setState(() => _phase = _Phase.checking);

    final RecordedTake take;
    try {
      take = await _takeRecorder.stop();
    } on TakeRecorderException catch (e) {
      _showProblem(e.message);
      return;
    }
    if (!mounted) return;
    final step = _step;
    final String? filePath = take.filePath;
    final List<int>? bytes = take.bytes;

    try {
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
        await TakeRecorder.deleteFile(filePath);
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
      await TakeRecorder.deleteFile(filePath);
      _showProblem(e.report.userMessage);
    } catch (e) {
      await TakeRecorder.deleteFile(filePath);
      _showProblem(e.toString());
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
      await TakeRecorder.deleteFile(_vowelPath);
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
      backgroundColor: GateColors.bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: GateColors.textPrimary,
        title: const Text(
          'Voice Screening Test',
          style: TextStyle(fontWeight: FontWeight.w700, color: GateColors.textPrimary, fontSize: 18),
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
              color: passed ? GateColors.accent : (active ? GateColors.accent.withValues(alpha: 0.45) : GateColors.stroke),
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
            color: GateColors.accent.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            'STEP ${_stepIndex + 1} OF ${_steps.length}  ·  ${step.title.toUpperCase()}',
            style: const TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w800,
              color: GateColors.accent,
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
          style: const TextStyle(fontSize: 15, color: GateColors.textSecondary, height: 1.45),
        ),
        const SizedBox(height: 14),
        Text(
          step.prompt,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: GateColors.textPrimary),
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
                    ? const [Color(0xFFFF8A65), GateColors.danger]
                    : busy
                        ? const [GateColors.surfaceRaised, GateColors.surfaceRaised]
                        : const [GateColors.accent, GateColors.accentDim],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: busy
                  ? null
                  : [
                      BoxShadow(
                        color: (_phase == _Phase.recording ? GateColors.danger : GateColors.accent).withValues(alpha: 0.35),
                        blurRadius: 24,
                        offset: const Offset(0, 8),
                      ),
                    ],
            ),
            child: Icon(
              _phase == _Phase.recording ? Icons.stop_rounded : Icons.mic_rounded,
              size: 46,
              color: busy ? GateColors.textFaint : const Color(0xFF071210),
            ),
          ),
        ),
        const SizedBox(height: 14),
        Text(
          _micLabel(),
          style: const TextStyle(fontSize: 13, color: GateColors.textFaint, fontWeight: FontWeight.w600),
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
            _countdownNumber('$_remaining', GateColors.accent),
            const Text('Listening...', style: TextStyle(color: GateColors.accent, fontWeight: FontWeight.w600)),
          ],
        );
      case _Phase.checking:
        // The countdown finished at 0; keep the 0 on screen while the gate checks the take.
        return Column(
          children: [
            _countdownNumber('0', GateColors.textFaint),
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
            color: GateColors.danger.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: GateColors.danger.withValues(alpha: 0.4)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.error_outline_rounded, color: GateColors.danger, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  _message ?? 'Please record again.',
                  style: const TextStyle(color: GateColors.textPrimary, fontSize: 13.5, height: 1.4),
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
            child: Text('Ready when you are', style: TextStyle(color: GateColors.textSecondary, fontSize: 14)),
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
            child: CircularProgressIndicator(strokeWidth: 3, color: GateColors.accent),
          ),
          const SizedBox(height: 12),
          Text(label, style: const TextStyle(color: GateColors.textSecondary, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _buildPassedChip(String label, QualityReport? report) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: GateColors.accent.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: GateColors.accent.withValues(alpha: 0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.check_circle_rounded, color: GateColors.accent, size: 18),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              report == null ? label : '$label (score ${report.qualityScore.toStringAsFixed(0)})',
              style: const TextStyle(color: GateColors.textPrimary, fontSize: 12.5, fontWeight: FontWeight.w600),
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
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: GateColors.textPrimary),
        ),
        const SizedBox(height: 6),
        const Text(
          'Both recordings passed the quality check.',
          style: TextStyle(fontSize: 13.5, color: GateColors.textSecondary),
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
            style: TextStyle(color: GateColors.textSecondary, fontSize: 13.5),
          ),
        ),
        const SizedBox(height: 18),
        const Text(
          'This is a screening aid, not a diagnosis. Please consult a doctor about any concerns.',
          style: TextStyle(color: GateColors.textFaint, fontSize: 12, height: 1.4),
        ),
        const SizedBox(height: 22),
        ElevatedButton(
          onPressed: () => Navigator.of(context).maybePop(),
          style: ElevatedButton.styleFrom(
            backgroundColor: GateColors.accent,
            foregroundColor: const Color(0xFF071210),
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          ),
          child: const Text('Done', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
        ),
        const SizedBox(height: 10),
        TextButton(
          onPressed: _restart,
          child: const Text('Run the test again', style: TextStyle(color: GateColors.accent, fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }

  Widget _buildPhonationBody() {
    if (_phonationError != null) {
      return Text(
        'Could not get the phonation result: $_phonationError',
        style: const TextStyle(color: GateColors.warn, fontSize: 13, height: 1.4),
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
            color: pd ? GateColors.warn : GateColors.accent,
            fontSize: 15,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          'PD probability: ${(r.probabilityPd * 100).toStringAsFixed(0)}%',
          style: const TextStyle(color: GateColors.textSecondary, fontSize: 13),
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
        color: GateColors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: GateColors.stroke),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: GateColors.accent, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(color: GateColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                stepLabel,
                style: const TextStyle(color: GateColors.textFaint, fontSize: 11, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            report == null
                ? 'Quality gate: off'
                : 'Quality gate: PASS · score ${report.qualityScore.toStringAsFixed(0)} · ${report.audioChoice ?? '-'} audio',
            style: const TextStyle(color: GateColors.textFaint, fontSize: 12),
          ),
          const SizedBox(height: 10),
          body,
        ],
      ),
    );
  }
}
