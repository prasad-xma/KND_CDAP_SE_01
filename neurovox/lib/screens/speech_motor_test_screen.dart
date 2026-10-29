import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import '../core/i18n/language_controller.dart';
import '../core/models/ddk_result.dart';
import '../core/services/ddk_api_service.dart';
import '../core/widgets/language_toggle_button.dart';
import '../core/models/speech_motor_result.dart';

class SpeechMotorTestScreen extends StatefulWidget {
  final VoidCallback? onClose;
  final ValueChanged<DdkResult>? onResult;
//   final ValueChanged<SpeechMotorResult>? onResult;

  const SpeechMotorTestScreen({super.key, this.onClose, this.onResult});

  @override
  State<SpeechMotorTestScreen> createState() => _SpeechMotorTestScreenState();
}

class _SpeechMotorTestScreenState extends State<SpeechMotorTestScreen> {
  final AudioRecorder _recorder = AudioRecorder();
  Timer? _timer;
  bool _isRecording = false;
  bool _isProcessing = false;
  bool _isInstructionCountdown = false;
  int _secondsRemaining = 6;
  int _instructionSecondsRemaining = 5;
  String _task = 'pa';
  String? _paPath;
  String? _error;
  DdkResult? _result;

  @override
  void dispose() {
    _timer?.cancel();
    _recorder.dispose();
    super.dispose();
  }

  Future<String> _recordingPath(String task) async {
    final directory = Directory.systemTemp;
    return '${directory.path}${Platform.pathSeparator}ddk_${task}_${DateTime.now().millisecondsSinceEpoch}.wav';
  }

  Future<void> _startRecording() async {
    final permission = await Permission.microphone.request();
    if (!permission.isGranted || !await _recorder.hasPermission()) {
      setState(() => _error = 'Microphone permission is required.');
      return;
    }

    final path = await _recordingPath(_task);
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.wav,
        sampleRate: 44100,
        numChannels: 1,
      ),
      path: path,
    );
    setState(() {
      _isRecording = true;
      _secondsRemaining = 6;
      _error = null;
    });
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_secondsRemaining <= 1) {
        timer.cancel();
        _stopRecording();
      } else {
        setState(() => _secondsRemaining--);
      }
    });
  }

  void _beginTask() {
    if (_isInstructionCountdown || _isRecording || _isProcessing) return;
    setState(() {
      _isInstructionCountdown = true;
      _instructionSecondsRemaining = 5;
      _error = null;
    });
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_instructionSecondsRemaining <= 1) {
        timer.cancel();
        _timer = null;
        if (!mounted) return;
        setState(() => _isInstructionCountdown = false);
        _startRecording();
      } else if (mounted) {
        setState(() => _instructionSecondsRemaining--);
      }
    });
  }

  Future<void> _stopRecording() async {
    _timer?.cancel();
    _timer = null;
    final path = await _recorder.stop();
    if (!mounted) return;
    setState(() => _isRecording = false);
    if (path == null) {
      setState(() => _error = 'Recording failed. Please try again.');
      return;
    }
    if (_task == 'pa') {
      setState(() {
        _paPath = path;
        _task = 'ta';
        _error = null;
      });
      _beginTask();
    } else {
      await _submit(path);
    }
  }

  Future<void> _submit(String taPath) async {
    final paPath = _paPath;
    if (paPath == null) {
      setState(
        () => _error = 'The pa recording is missing. Please restart the test.',
      );
      return;
    }
    setState(() {
      _isProcessing = true;
      _error = null;
    });
    try {
      final result = await DdkApiService.screenDualRecording(
        paFilePath: paPath,
        taFilePath: taPath,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _isProcessing = false;
      });
      widget.onResult?.call(result);
      await _deleteTemporaryFiles(paPath, taPath);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
        _error = error.toString();
      });
      await _deleteTemporaryFiles(paPath, taPath);
    }
  }

  Future<void> _deleteTemporaryFiles(String paPath, String taPath) async {
    for (final path in [paPath, taPath]) {
      final file = File(path);
      if (await file.exists()) await file.delete();
    }
  }

  void _restart() {
    setState(() {
      _task = 'pa';
      _paPath = null;
      _result = null;
      _error = null;
      _isInstructionCountdown = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    const primaryBlue = Color(0xFF2563EB);
    const darkSlate = Color(0xFF1E293B);
    const mediumGrey = Color(0xFF64748B);
    final result = _result;

    return ListenableBuilder(
      listenable: LanguageController.instance,
      builder: (context, _) => SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        tr('motorTitle'),
                        style: const TextStyle(
                          fontSize: 26,
                          fontWeight: FontWeight.w800,
                          color: darkSlate,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        tr('motorSubtitle'),
                        style: const TextStyle(fontSize: 14, color: mediumGrey),
                      ),
                      
                    ],
                  ),
                ),
                const LanguageToggleButton(activeColor: primaryBlue),
                if (widget.onClose != null)
                  IconButton(
                    onPressed: widget.onClose,
                    icon: const Icon(Icons.close),
                  ),
              ],
            ),
            const SizedBox(height: 24),
            _instructionCard(
              '1',
              tr('ddkPaTaskTitle'),
              tr('ddkPaTaskInstruction'),
              Icons.record_voice_over,
            ),
            _instructionCard(
              '2',
              tr('ddkTaTaskTitle'),
              tr('ddkTaTaskInstruction'),
              Icons.record_voice_over,
            ),
            const SizedBox(height: 12),
            if (_isRecording)
              Center(
                child: Text(
                  '${tr('ddkRecordingPrefix')} ${_task.toUpperCase()} — $_secondsRemaining ${tr('secondsRemainingSuffix')}',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: primaryBlue,
                  ),
                ),
              )
            else if (_isInstructionCountdown)
              Center(
                child: Text(
                  '${tr('ddkGetReady')} $_instructionSecondsRemaining ${tr('secondsRemainingSuffix')}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: primaryBlue,
                  ),
                ),
              )
            else if (_isProcessing)
              const Center(child: CircularProgressIndicator())
            else if (result == null)
              Center(
                child: ElevatedButton.icon(
                  onPressed: _beginTask,
                  icon: const Icon(Icons.mic),
                  label: Text(
                    _task == 'pa' ? tr('startPaTask') : tr('startTaTask'),
                  ),
                  /*
                    ),
                    const SizedBox(height: 10),
                    Text(
                      tr('motorNotAvailableDesc'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: mediumGrey, fontSize: 14, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 18),
                    OutlinedButton(
                      onPressed: () {
                        widget.onResult?.call(SpeechMotorResult.placeholder());
                        widget.onClose?.call();
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: primaryBlue,
                        side: const BorderSide(color: primaryBlue),
                        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                      child: Text(
                        tr('motorUsePlaceholderButton'),
                        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      tr('motorUsePlaceholderNote'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: mediumGrey, fontSize: 11.5, fontStyle: FontStyle.italic),
                    ),
                  ], */
                  
                ),
              ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Colors.red)),
            ],
            if (result != null) ...[
              const SizedBox(height: 20),
              _resultCard(result.paResult),
              _resultCard(result.taResult),
              Text(
                '${tr('meanPdProbability')}: ${(result.meanPdProbability * 100).toStringAsFixed(1)}%',
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  color: darkSlate,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                result.interpretationNote,
                style: const TextStyle(color: mediumGrey),
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _restart,
                child: Text(tr('recordAgain')),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _instructionCard(
    String step,
    String title,
    String description,
    IconData icon,
  ) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: Icon(icon, color: const Color(0xFF2563EB)),
        title: Text(
          '$step: $title',
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        subtitle: Text(description),
      ),
    );
  }

  Widget _resultCard(DdkRecordingResult result) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        title: Text(
          result.task,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        subtitle: Text(
          '${result.predictedClass} — PD probability ${(result.pdProbability * 100).toStringAsFixed(1)}%',
        ),
        trailing: Text(
          result.predictedClass,
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
    );
  }
}
