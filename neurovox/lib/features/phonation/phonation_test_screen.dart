import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import '../../core/models/phonation_result.dart';
import '../../core/services/phonation_api_service.dart';
import 'i18n/en_en.dart';
import 'i18n/sl_sl.dart';

class PhonationTestScreen extends StatefulWidget {
  const PhonationTestScreen({super.key});

  @override
  State<PhonationTestScreen> createState() => _PhonationTestScreenState();
}

class _PhonationTestScreenState extends State<PhonationTestScreen> with SingleTickerProviderStateMixin {
  final AudioRecorder _recorder = AudioRecorder();
  late final AnimationController _pulseController;

  bool _isRecording = false;
  bool _isProcessing = false;
  String? _recordError;
  PhonationResult? _lastResult;

  /// Which measurement approach to use - see PhonationApiService for the
  /// full explanation. Exposed as a toggle so both can be tried on the same
  /// recording and compared.
  bool _extractVowelSegment = false;

  /// Language this screen's text is shown in. Only affects this screen.
  bool _isEnglish = true;

  String _s(String key) => _isEnglish ? enEnStrings[key]! : slSlStrings[key]!;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _recorder.dispose();
    super.dispose();
  }

  Future<String> _newRecordingPath() async {
    if (kIsWeb) return 'phonation_recording.wav';
    final dir = await getTemporaryDirectory();
    final ts = DateTime.now().millisecondsSinceEpoch;
    return '${dir.path}/phonation_recording_$ts.wav';
  }

  Future<void> _startRecording() async {
    if (!kIsWeb) {
      final status = await Permission.microphone.request();
      if (!status.isGranted) {
        setState(() => _recordError = _s('micPermission'));
        return;
      }
    }
    if (!await _recorder.hasPermission()) {
      setState(() => _recordError = _s('micPermission'));
      return;
    }

    final path = await _newRecordingPath();
    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 44100, numChannels: 1),
      path: path,
    );
    setState(() {
      _isRecording = true;
      _recordError = null;
    });
  }

  Future<void> _stopRecordingAndScreen(BuildContext modalContext) async {
    final path = await _recorder.stop();
    setState(() {
      _isRecording = false;
      _isProcessing = true;
    });

    if (path == null) {
      setState(() {
        _isProcessing = false;
        _recordError = _s('recordingFailed');
      });
      return;
    }

    try {
      final PhonationResult result;
      if (kIsWeb) {
        final blobResponse = await http.get(Uri.parse(path));
        final bytes = blobResponse.bodyBytes;
        if (bytes.length < 1000) {
          throw Exception(
            'Recording looks too short/empty (${bytes.length} bytes) - the mic may not '
            'have actually captured audio. Try recording again, speaking clearly for the '
            'full duration.',
          );
        }
        result = await PhonationApiService.screenVowelRecordingBytes(
          bytes,
          extractVowelSegment: _extractVowelSegment,
        );
      } else {
        result = await PhonationApiService.screenVowelRecording(
          path,
          extractVowelSegment: _extractVowelSegment,
        );
      }
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
        _lastResult = result;
      });
      if (modalContext.mounted) Navigator.pop(modalContext);
      _showSuccessAssessmentDialog(result);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
        _recordError = e.toString();
      });
    } finally {
      if (!kIsWeb) {
        final f = File(path);
        if (await f.exists()) {
          await f.delete();
        }
      }
    }
  }

  void _showRecordVoiceModal() {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color primaryTealLight = Color(0xFF0EC4B7);
    const Color darkGrey = Color(0xFF2D3748);
    const Color lightGrey = Color(0xFF718096);

    setState(() => _recordError = null);

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (modalContext) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Container(
              height: MediaQuery.of(context).size.height * 0.72,
              decoration: const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.vertical(top: Radius.circular(32)),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
              child: Column(
                children: [
                  Container(
                    width: 44,
                    height: 5,
                    decoration: BoxDecoration(
                      color: Colors.grey.shade300,
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _s('modalTitle'),
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          color: darkGrey,
                        ),
                      ),
                      IconButton(
                        onPressed: () => Navigator.pop(modalContext),
                        icon: const Icon(Icons.close_rounded, color: lightGrey),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _s('modalInstruction'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 14,
                      color: lightGrey,
                      height: 1.4,
                    ),
                  ),
                  const Spacer(),
                  SizedBox(
                    height: 100,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: List.generate(24, (index) {
                        final double barHeight = _isRecording
                            ? 15.0 + 65.0 * math.sin((index * 0.3) + (_pulseController.value * math.pi * 2)).abs()
                            : 8.0 + (index % 4) * 4.0;

                        return Container(
                          margin: const EdgeInsets.symmetric(horizontal: 2.5),
                          width: 4,
                          height: barHeight,
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [primaryTealLight, primaryTeal],
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                            ),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        );
                      }),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    _isProcessing
                        ? _s('analyzing')
                        : _isRecording
                            ? _s('listening')
                            : _s('readyToRecord'),
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: _isRecording ? primaryTeal : lightGrey,
                    ),
                  ),
                  if (_recordError != null) ...[
                    const SizedBox(height: 10),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      child: Text(
                        _recordError!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 12, color: Colors.redAccent),
                      ),
                    ),
                  ],
                  const Spacer(),
                  GestureDetector(
                    onTap: _isProcessing
                        ? null
                        : () async {
                            if (!_isRecording) {
                              await _startRecording();
                            } else {
                              await _stopRecordingAndScreen(modalContext);
                            }
                            if (modalContext.mounted) setModalState(() {});
                          },
                    child: Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: LinearGradient(
                          colors: _isProcessing
                              ? [Colors.grey.shade400, Colors.grey.shade500]
                              : _isRecording
                                  ? [Colors.redAccent, Colors.red]
                                  : [primaryTealLight, primaryTeal],
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: (_isRecording ? Colors.red : primaryTeal).withValues(alpha: 0.4),
                            blurRadius: 24,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      child: _isProcessing
                          ? const Padding(
                              padding: EdgeInsets.all(22),
                              child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3),
                            )
                          : Icon(
                              _isRecording ? Icons.stop_rounded : Icons.mic_rounded,
                              color: Colors.white,
                              size: 38,
                            ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    _isProcessing
                        ? _s('pleaseWait')
                        : _isRecording
                            ? _s('tapToStop')
                            : _s('tapToStart'),
                    style: const TextStyle(fontSize: 13, color: lightGrey),
                  ),
                  const SizedBox(height: 12),
                ],
              ),
            );
          },
        );
      },
    );
  }

  void _showSuccessAssessmentDialog(PhonationResult result) {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color warnAmber = Color(0xFFD97706);

    final bool flagged = result.isPd;
    final double confidence = flagged ? result.probabilityPd : result.probabilityHc;
    final Color accent = flagged ? warnAmber : primaryTeal;

    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
          backgroundColor: Colors.white,
          title: Row(
            children: [
              Icon(Icons.check_circle_rounded, color: accent, size: 28),
              const SizedBox(width: 10),
              Text(
                _s('analysisComplete'),
                style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                result.modelUsed == 'readtext' ? _s('resultIntroReadtext') : _s('resultIntro'),
                style: const TextStyle(color: Color(0xFF4A4A4A), fontSize: 13),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      _s('modelPrediction'),
                      style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF2D3748)),
                    ),
                    Text(
                      '${flagged ? _s("pdIndicators") : _s("hcRange")} '
                      '(${(confidence * 100).toStringAsFixed(1)}%)',
                      style: TextStyle(fontWeight: FontWeight.w800, color: accent),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),
              Text(
                result.extractionUsed
                    ? '${_s("modeSegment")} '
                        '(${result.segmentStartSeconds?.toStringAsFixed(2)}s-'
                        '${result.segmentEndSeconds?.toStringAsFixed(2)}s, '
                        '${result.segmentDurationSeconds?.toStringAsFixed(2)}s)'
                    : _s('modeWhole'),
                style: const TextStyle(color: Color(0xFF64748B), fontSize: 11),
              ),
              const SizedBox(height: 4),
              Text(
                _s('disclaimer'),
                style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontStyle: FontStyle.italic),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: Text(
                _s('closeButton'),
                style: const TextStyle(color: primaryTeal, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildMetricRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF2D3748), fontSize: 13)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF0C9388), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildLanguageToggle(Color primaryTeal) {
    Widget pill(String label, bool selectedWhenEnglish) {
      final bool selected = _isEnglish == selectedWhenEnglish;
      return Expanded(
        child: GestureDetector(
          onTap: () => setState(() => _isEnglish = selectedWhenEnglish),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(
              color: selected ? primaryTeal : Colors.transparent,
              borderRadius: BorderRadius.circular(12),
            ),
            alignment: Alignment.center,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: selected ? Colors.white : const Color(0xFF64748B),
              ),
            ),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          pill('English', true),
          pill('සිංහල', false),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    final features = _lastResult?.features;

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildLanguageToggle(primaryTeal),
          const SizedBox(height: 20),
          Text(
            _s('title'),
            style: const TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            _s('subtitle'),
            style: const TextStyle(fontSize: 14, color: mediumGrey, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 24),

          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: primaryTeal.withValues(alpha: 0.08),
                  blurRadius: 18,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: Column(
              children: [
                Container(
                  width: 90,
                  height: 90,
                  decoration: const BoxDecoration(
                    color: Color(0xFFD6ECE6),
                    shape: BoxShape.circle,
                  ),
                  child: const Center(
                    child: Icon(Icons.record_voice_over_rounded, size: 48, color: primaryTeal),
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  _s('taskTitle'),
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: darkSlate),
                ),
                const SizedBox(height: 10),
                Text(
                  _s('taskDesc'),
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 14, color: mediumGrey, height: 1.5),
                ),
                const SizedBox(height: 18),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          _extractVowelSegment ? _s('toggleExtractOn') : _s('toggleExtractOff'),
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF2D3748)),
                        ),
                      ),
                      Switch(
                        value: _extractVowelSegment,
                        activeTrackColor: primaryTeal,
                        onChanged: (value) => setState(() => _extractVowelSegment = value),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                ElevatedButton.icon(
                  onPressed: _showRecordVoiceModal,
                  icon: const Icon(Icons.play_arrow_rounded, color: Colors.white),
                  label: Text(
                    _s('beginButton'),
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: primaryTeal,
                    minimumSize: const Size(double.infinity, 54),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Diagnostic Metrics Preview - real values from the last recording, if any.
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: primaryTeal.withValues(alpha: 0.06),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(_s('metricsTitle'), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 14),
                if (features == null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text(
                      _s('noRecordingYet'),
                      style: const TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
                    ),
                  )
                else ...[
                  Text(
                    _lastResult!.extractionUsed
                        ? '${_s("fromSegment")} (${_lastResult!.segmentDurationSeconds?.toStringAsFixed(2)}s)'
                        : _s('fromWhole'),
                    style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8), fontStyle: FontStyle.italic),
                  ),
                  const SizedBox(height: 10),
                  _buildMetricRow(_s('f0'), '${features['mean_f0']!.toStringAsFixed(1)} Hz'),
                  const Divider(),
                  _buildMetricRow(_s('jitter'), '${(features['jitter']! * 100).toStringAsFixed(2)}%'),
                  const Divider(),
                  _buildMetricRow(_s('shimmer'), '${(features['shimmer']! * 100).toStringAsFixed(2)}%'),
                  const Divider(),
                  _buildMetricRow(_s('hnr'), '${features['hnr']!.toStringAsFixed(1)} dB'),
                ],
              ],
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }
}
