import 'dart:async';
import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import '../../core/i18n/language_controller.dart';
import '../../core/models/phonation_result.dart';
import '../../core/services/phonation_api_service.dart';

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

class PhonationTestScreen extends StatefulWidget {
  final VoidCallback? onClose;
  final ValueChanged<PhonationDualResult>? onResult;

  const PhonationTestScreen({super.key, this.onClose, this.onResult});

  @override
  State<PhonationTestScreen> createState() => _PhonationTestScreenState();
}

class _PhonationTestScreenState extends State<PhonationTestScreen> with SingleTickerProviderStateMixin {
  final AudioRecorder _recorder = AudioRecorder();
  late final AnimationController _pulseController;

  bool _isRecording = false;
  bool _isProcessing = false;
  String? _recordError;
  PhonationDualResult? _lastResult;

  int _currentStep = 1;

  String? _vowelFilePath;
  List<int>? _vowelFileBytes;

  // Step 1 records the vowel task _vowelRepeatCount times and averages the
  // predictions - reduces take-to-take measurement noise vs a single
  // recording (see PhonationMultiResult.toAveragedResult).
  static const int _vowelRepeatCount = 3;
  int _vowelRepeatIndex = 0;
  final List<String> _vowelMultiFilePaths = [];
  final List<List<int>> _vowelMultiByteLists = [];

  static const int _vowelRecordSeconds = 3;
  int _vowelCountdownRemaining = _vowelRecordSeconds;
  Timer? _vowelCountdownTimer;

  void _cancelVowelCountdown() {
    _vowelCountdownTimer?.cancel();
    _vowelCountdownTimer = null;
  }

  void _startVowelCountdown(
    BuildContext modalContext,
    void Function(void Function()) setModalState,
  ) {
    _vowelCountdownRemaining = _vowelRecordSeconds;
    _vowelCountdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) async {
      _vowelCountdownRemaining--;
      if (_vowelCountdownRemaining <= 0) {
        timer.cancel();
        _vowelCountdownTimer = null;
        if (_isRecording) {
          await _stopStepAndAdvance(modalContext, setModalState);
        }
        return;
      }
      if (modalContext.mounted) setModalState(() {});
    });
  }

  bool _extractVowelSegment = false;

  static const bool _showAdvancedToggles = false;

  static const bool _includePhraseTask = false;

  bool _showMoreVowelParams = false;
  bool _showMorePhraseParams = false;

  String _s(String key) => tr(key);

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
    _cancelVowelCountdown();
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

  Future<void> _resetStepState() async {
    _cancelVowelCountdown();
    if (!kIsWeb && _vowelFilePath != null) {
      final f = File(_vowelFilePath!);
      if (await f.exists()) await f.delete();
    }
    _vowelFilePath = null;
    _vowelFileBytes = null;
    if (!kIsWeb) {
      for (final p in _vowelMultiFilePaths) {
        final f = File(p);
        if (await f.exists()) await f.delete();
      }
    }
    _vowelMultiFilePaths.clear();
    _vowelMultiByteLists.clear();
    _vowelRepeatIndex = 0;
    _currentStep = 1;
    _vowelCountdownRemaining = _vowelRecordSeconds;
  }

  Future<void> _stopStepAndAdvance(
    BuildContext modalContext,
    void Function(void Function()) setModalState,
  ) async {
    _cancelVowelCountdown();
    final path = await _recorder.stop();
    setState(() => _isRecording = false);

    if (path == null) {
      setState(() => _recordError = _s('recordingFailed'));
      return;
    }

    if (_currentStep == 1 && !_includePhraseTask) {
      // Stash this repeat's recording.
      try {
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
          _vowelMultiByteLists.add(bytes);
        } else {
          _vowelMultiFilePaths.add(path);
        }
      } catch (e) {
        setState(() => _recordError = e.toString());
        return;
      }

      final bool hasMoreRepeats = (kIsWeb ? _vowelMultiByteLists.length : _vowelMultiFilePaths.length) <
          _vowelRepeatCount;
      if (hasMoreRepeats) {
        setState(() {
          _vowelRepeatIndex++;
          _recordError = null;
        });
        setModalState(() {});
        return;
      }

      // All repeats captured - score them together and average.
      setState(() => _isProcessing = true);
      try {
        final PhonationMultiResult multiResult = kIsWeb
            ? await PhonationApiService.screenVowelMultiBytes(_vowelMultiByteLists)
            : await PhonationApiService.screenVowelMulti(_vowelMultiFilePaths);
        if (!mounted) return;
        final dualResult = PhonationDualResult.vowelOnly(multiResult.toAveragedResult());
        setState(() {
          _isProcessing = false;
          _lastResult = dualResult;
        });
        widget.onResult?.call(dualResult);
        if (modalContext.mounted) Navigator.pop(modalContext);
      } catch (e) {
        if (!mounted) return;
        setState(() {
          _isProcessing = false;
          _recordError = e.toString();
        });
      } finally {
        await _resetStepState();
      }
      return;
    }

    if (_currentStep == 1) {
      try {
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
          _vowelFileBytes = bytes;
        } else {
          _vowelFilePath = path;
        }
      } catch (e) {
        setState(() => _recordError = e.toString());
        return;
      }
      setState(() {
        _currentStep = 2;
        _recordError = null;
      });
      setModalState(() {});
      return;
    }

    setState(() => _isProcessing = true);
    try {
      final PhonationDualResult result;
      if (kIsWeb) {
        final blobResponse = await http.get(Uri.parse(path));
        final phraseBytes = blobResponse.bodyBytes;
        if (phraseBytes.length < 1000) {
          throw Exception(
            'Recording looks too short/empty (${phraseBytes.length} bytes) - the mic may not '
            'have actually captured audio. Try recording again, speaking clearly for the '
            'full duration.',
          );
        }
        result = await PhonationApiService.screenDualRecordingBytes(
          vowelBytes: _vowelFileBytes!,
          phraseBytes: phraseBytes,
        );
      } else {
        result = await PhonationApiService.screenDualRecording(
          vowelFilePath: _vowelFilePath!,
          phraseFilePath: path,
        );
      }
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
        _lastResult = result;
      });
      widget.onResult?.call(result);
      if (modalContext.mounted) Navigator.pop(modalContext);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
        _recordError = e.toString();
      });
    } finally {
      if (!kIsWeb) {
        final f = File(path);
        if (await f.exists()) await f.delete();
      }
      await _resetStepState();
    }
  }

  void _showRecordVoiceModal() {
    setState(() {
      _recordError = null;
      _currentStep = 1;
    });

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (modalContext) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            final bool isStep1 = _currentStep == 1;
            return Container(
              height: MediaQuery.of(context).size.height * 0.72,
              decoration: const BoxDecoration(
                color: _surface,
                borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
                border: Border(top: BorderSide(color: _stroke)),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
              child: Column(
                children: [
                  Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: _stroke,
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      if (_includePhraseTask)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: _accent.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            isStep1 ? _s('step1Badge') : _s('step2Badge'),
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                              color: _accent,
                              letterSpacing: 0.4,
                            ),
                          ),
                        )
                      else if (isStep1)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: _accent.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            '${_s('recordingBadgePrefix')} ${_vowelRepeatIndex + 1}/$_vowelRepeatCount',
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                              color: _accent,
                              letterSpacing: 0.4,
                            ),
                          ),
                        )
                      else
                        const SizedBox.shrink(),
                      IconButton(
                        onPressed: () async {
                          await _resetStepState();
                          if (modalContext.mounted) Navigator.pop(modalContext);
                        },
                        icon: const Icon(Icons.close_rounded, color: _textSecondary),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    isStep1 ? _s('step1Title') : _s('modalTitle'),
                    style: const TextStyle(
                      fontSize: 19,
                      fontWeight: FontWeight.w700,
                      color: _textPrimary,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    isStep1 ? _s('step1Instruction') : _s('modalInstruction'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 13.5,
                      color: _textSecondary,
                      height: 1.4,
                    ),
                  ),
                  const Spacer(),
                  SizedBox(
                    height: 90,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: List.generate(24, (index) {
                        final double barHeight = _isRecording
                            ? 14.0 + 60.0 * math.sin((index * 0.3) + (_pulseController.value * math.pi * 2)).abs()
                            : 6.0 + (index % 4) * 3.0;

                        return Container(
                          margin: const EdgeInsets.symmetric(horizontal: 2.5),
                          width: 4,
                          height: barHeight,
                          decoration: BoxDecoration(
                            color: _isRecording ? _accent : _stroke,
                            borderRadius: BorderRadius.circular(4),
                          ),
                        );
                      }),
                    ),
                  ),
                  const SizedBox(height: 18),
                  if (isStep1 && _isRecording) ...[
                    Text(
                      '$_vowelCountdownRemaining',
                      style: const TextStyle(
                        fontSize: 40,
                        fontWeight: FontWeight.w800,
                        color: _accent,
                        fontFeatures: [FontFeature.tabularFigures()],
                      ),
                    ),
                    const SizedBox(height: 4),
                  ],
                  Text(
                    _isProcessing
                        ? _s('analyzing')
                        : _isRecording
                            ? _s('listening')
                            : (isStep1 && !_includePhraseTask && _vowelRepeatIndex > 0)
                                ? _s('recordingCapturedNext')
                                : _s('readyToRecord'),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: _isRecording ? _accent : _textSecondary,
                    ),
                  ),
                  if (_recordError != null) ...[
                    const SizedBox(height: 10),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      child: Text(
                        _recordError!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 12, color: _danger),
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
                              if (!modalContext.mounted) return;
                              if (isStep1 && _isRecording) {
                                _startVowelCountdown(modalContext, setModalState);
                              }
                            } else {
                              await _stopStepAndAdvance(modalContext, setModalState);
                            }
                            if (modalContext.mounted) setModalState(() {});
                          },
                    child: Container(
                      width: 92,
                      height: 92,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: _isProcessing
                            ? const LinearGradient(colors: [_stroke, _stroke])
                            : _isRecording
                                ? const LinearGradient(colors: [Color(0xFFFF8A65), _danger])
                                : const LinearGradient(colors: [_accent, _accentDim]),
                        boxShadow: [
                          BoxShadow(
                            color: (_isRecording ? _danger : _accent).withValues(alpha: 0.35),
                            blurRadius: 28,
                            spreadRadius: 2,
                          ),
                        ],
                      ),
                      child: _isProcessing
                          ? const Padding(
                              padding: EdgeInsets.all(26),
                              child: CircularProgressIndicator(color: _textPrimary, strokeWidth: 3),
                            )
                          : Icon(
                              _isRecording ? Icons.stop_rounded : Icons.mic_rounded,
                              color: const Color(0xFF071210),
                              size: 40,
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
                    style: const TextStyle(fontSize: 12.5, color: _textFaint),
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

  Widget _buildConfidenceGauge(double value, Color color) {
    const double gaugeWidth = 168;
    return SizedBox(
      width: gaugeWidth,
      height: gaugeWidth / 2 + 38,
      child: Stack(
        alignment: Alignment.topCenter,
        children: [
          SizedBox(
            width: gaugeWidth,
            height: gaugeWidth / 2,
            child: CustomPaint(painter: _GaugePainter(value: value, color: color)),
          ),
          Positioned(
            top: gaugeWidth / 2 - 14,
            child: Text(
              '${(value * 100).toStringAsFixed(1)}%',
              style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: color),
            ),
          ),
        ],
      ),
    );
  }

  Widget _subScoreBadge({required String label, required PhonationResult result}) {
    final bool flagged = result.isPd;
    final double confidence = flagged ? result.probabilityPd : result.probabilityHc;
    final Color accent = flagged ? _warn : _accent;

    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: _surfaceRaised,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _stroke),
        ),
        child: Column(
          children: [
            Text(
              label,
              style: const TextStyle(fontSize: 11, color: _textSecondary, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 4),
            Text(
              '${(confidence * 100).toStringAsFixed(1)}%',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: accent),
            ),
            Text(
              flagged ? _s('pdIndicators') : _s('hcRange'),
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 10, color: accent, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultCenterpiece(PhonationDualResult result) {
    final bool flagged = result.isPd;
    final double confidence = flagged ? result.probabilityPd : result.probabilityHc;
    final Color accent = flagged ? _warn : _accent;

    return Column(
      children: [
        _buildConfidenceGauge(confidence, accent),
        const SizedBox(height: 4),
        Text(
          flagged ? _s('pdIndicators') : _s('hcRange'),
          style: TextStyle(fontWeight: FontWeight.w800, color: accent, fontSize: 16),
        ),
        const SizedBox(height: 10),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Text(
            result.phraseTask != null ? _s('resultIntroDual') : _s('resultIntro'),
            textAlign: TextAlign.center,
            style: const TextStyle(color: _textSecondary, fontSize: 12, height: 1.4),
          ),
        ),
        if (result.phraseTask != null) ...[
          const SizedBox(height: 14),
          Row(
            children: [
              _subScoreBadge(label: _s('vowelTaskLabel'), result: result.vowelTask),
              const SizedBox(width: 10),
              _subScoreBadge(label: _s('phraseTaskLabel'), result: result.phraseTask!),
            ],
          ),
        ],
        const SizedBox(height: 10),
        Text(
          _s('disclaimer'),
          textAlign: TextAlign.center,
          style: const TextStyle(color: _textFaint, fontSize: 11, fontStyle: FontStyle.italic),
        ),
      ],
    );
  }

  Widget _statTile({
    required IconData icon,
    required String label,
    required String value,
    required String unit,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surfaceRaised,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _stroke),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 15, color: _accent),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(fontSize: 11.5, color: _textSecondary, fontWeight: FontWeight.w600),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                value,
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  color: _textPrimary,
                  fontFeatures: [FontFeature.tabularFigures()],
                ),
              ),
              const SizedBox(width: 4),
              Text(unit, style: const TextStyle(fontSize: 12, color: _textFaint, fontWeight: FontWeight.w600)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _reasonPoint({required bool isNormal, required String text}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            isNormal ? Icons.check_circle_rounded : Icons.warning_rounded,
            size: 16,
            color: isNormal ? _accent : _warn,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text, style: const TextStyle(fontSize: 12.5, color: _textSecondary, height: 1.4)),
          ),
        ],
      ),
    );
  }

  Widget _buildReasoningSection(Map<String, double> features) {
    final double jitterPct = features['jitter']! * 100;
    final double shimmerPct = features['shimmer']! * 100;
    final double hnr = features['hnr']!;

    final bool jitterNormal = jitterPct < 1.04;
    final bool shimmerNormal = shimmerPct < 3.81;
    final bool hnrNormal = hnr > 20.0;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surfaceRaised,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _stroke),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _s('reasonTitle'),
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: _textPrimary),
          ),
          const SizedBox(height: 12),
          _reasonPoint(
            isNormal: jitterNormal,
            text: '${_s('jitter')} ${jitterPct.toStringAsFixed(2)}% '
                '${jitterNormal ? _s('jitterNormalMsg') : _s('jitterHighMsg')}',
          ),
          _reasonPoint(
            isNormal: shimmerNormal,
            text: '${_s('shimmer')} ${shimmerPct.toStringAsFixed(2)}% '
                '${shimmerNormal ? _s('shimmerNormalMsg') : _s('shimmerHighMsg')}',
          ),
          _reasonPoint(
            isNormal: hnrNormal,
            text: '${_s('hnr')} ${hnr.toStringAsFixed(1)}dB '
                '${hnrNormal ? _s('hnrNormalMsg') : _s('hnrLowMsg')}',
          ),
          Text(
            _s('reasonDisclaimer'),
            style: const TextStyle(fontSize: 10.5, color: _textFaint, fontStyle: FontStyle.italic),
          ),
        ],
      ),
    );
  }

  Widget _buildTaskDetailSection({
    required String taskLabel,
    required PhonationResult result,
    required bool showMore,
    required VoidCallback onToggleShowMore,
  }) {
    final features = result.features;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Flexible(
              child: Text(
                '$taskLabel — ${_s("metricsTitle")}',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: _textPrimary),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 10),
            Flexible(
              child: Text(
                result.extractionUsed
                    ? '${_s("fromSegment")} (${result.segmentDurationSeconds?.toStringAsFixed(2)}s)'
                    : _s('fromWhole'),
                style: const TextStyle(fontSize: 10.5, color: _textFaint, fontStyle: FontStyle.italic),
                textAlign: TextAlign.right,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.45,
          children: [
            _statTile(
              icon: Icons.graphic_eq_rounded,
              label: _s('f0'),
              value: features['mean_f0']!.toStringAsFixed(1),
              unit: 'Hz',
            ),
            _statTile(
              icon: Icons.show_chart_rounded,
              label: _s('jitter'),
              value: (features['jitter']! * 100).toStringAsFixed(2),
              unit: '%',
            ),
            _statTile(
              icon: Icons.waves_rounded,
              label: _s('shimmer'),
              value: (features['shimmer']! * 100).toStringAsFixed(2),
              unit: '%',
            ),
            _statTile(
              icon: Icons.volume_up_rounded,
              label: _s('hnr'),
              value: features['hnr']!.toStringAsFixed(1),
              unit: 'dB',
            ),
          ],
        ),
        const SizedBox(height: 12),
        Center(
          child: TextButton.icon(
            onPressed: onToggleShowMore,
            style: TextButton.styleFrom(foregroundColor: _accent),
            icon: Icon(showMore ? Icons.expand_less_rounded : Icons.expand_more_rounded),
            label: Text(showMore ? _s('viewLessParams') : _s('viewMoreParams')),
          ),
        ),
        if (showMore) ...[
          const SizedBox(height: 4),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 1.45,
            children: [
              _statTile(
                icon: Icons.show_chart_rounded,
                label: _s('stdF0'),
                value: features['std_f0']!.toStringAsFixed(1),
                unit: 'Hz',
              ),
              _statTile(
                icon: Icons.trending_up_rounded,
                label: _s('maxF0'),
                value: features['max_f0']!.toStringAsFixed(1),
                unit: 'Hz',
              ),
              _statTile(
                icon: Icons.graphic_eq_rounded,
                label: _s('meanRms'),
                value: features['mean_rms']!.toStringAsFixed(4),
                unit: '',
              ),
              _statTile(
                icon: Icons.graphic_eq_rounded,
                label: _s('stdRms'),
                value: features['std_rms']!.toStringAsFixed(4),
                unit: '',
              ),
              _statTile(
                icon: Icons.waves_rounded,
                label: _s('meanZcr'),
                value: features['mean_zcr']!.toStringAsFixed(4),
                unit: '',
              ),
              _statTile(
                icon: Icons.waves_rounded,
                label: _s('stdZcr'),
                value: features['std_zcr']!.toStringAsFixed(4),
                unit: '',
              ),
            ],
          ),
        ],
        const SizedBox(height: 20),
        _buildReasoningSection(features),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final features = _lastResult?.vowelTask.features;

    return ListenableBuilder(
      listenable: LanguageController.instance,
      builder: (context, _) => SizedBox.expand(
      child: Container(
      color: _bg,
      child: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _s('title'),
                          style: const TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w800,
                            color: _textPrimary,
                            letterSpacing: -0.4,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          _s('subtitle'),
                          style: const TextStyle(fontSize: 13, color: _textSecondary, fontWeight: FontWeight.w500),
                        ),
                      ],
                    ),
                  ),
                  if (_lastResult != null)
                    IconButton(
                      onPressed: () {
                        setState(() {
                          _lastResult = null;
                          _showMoreVowelParams = false;
                          _showMorePhraseParams = false;
                        });
                        widget.onClose?.call();
                      },
                      icon: const Icon(Icons.close_rounded, color: _textSecondary),
                    ),
                ],
              ),
              const SizedBox(height: 16),

              Center(
                child: _lastResult == null
                    ? Column(
                        children: [
                          GestureDetector(
                            onTap: _showRecordVoiceModal,
                            child: Container(
                              width: 148,
                              height: 148,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                gradient: const RadialGradient(
                                  colors: [_surfaceRaised, _surface],
                                ),
                                border: Border.all(color: _accent.withValues(alpha: 0.4), width: 1.5),
                                boxShadow: [
                                  BoxShadow(
                                    color: _accent.withValues(alpha: 0.18),
                                    blurRadius: 36,
                                    spreadRadius: 4,
                                  ),
                                ],
                              ),
                              child: Center(
                                child: Container(
                                  width: 108,
                                  height: 108,
                                  decoration: const BoxDecoration(
                                    shape: BoxShape.circle,
                                    gradient: LinearGradient(
                                      begin: Alignment.topLeft,
                                      end: Alignment.bottomRight,
                                      colors: [_accent, _accentDim],
                                    ),
                                  ),
                                  child: const Icon(Icons.mic_rounded, color: Color(0xFF071210), size: 40),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            _includePhraseTask ? _s('taskTitle') : _s('step1Title'),
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: _textPrimary),
                          ),
                          const SizedBox(height: 6),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            child: Text(
                              _includePhraseTask ? _s('taskDesc') : _s('step1Instruction'),
                              textAlign: TextAlign.center,
                              style: const TextStyle(fontSize: 12.5, color: _textSecondary, height: 1.5),
                            ),
                          ),
                        ],
                      )
                    : _buildResultCenterpiece(_lastResult!),
              ),

              if (_showAdvancedToggles) ...[
                const SizedBox(height: 20),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: _surfaceRaised,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: _stroke),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          _extractVowelSegment ? _s('toggleExtractOn') : _s('toggleExtractOff'),
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _textPrimary),
                        ),
                      ),
                      Switch(
                        value: _extractVowelSegment,
                        activeTrackColor: _accentDim,
                        onChanged: (value) => setState(() => _extractVowelSegment = value),
                      ),
                    ],
                  ),
                ),
              ],

              if (features != null) ...[
                const SizedBox(height: 30),
                _buildTaskDetailSection(
                  taskLabel: _s('vowelTaskLabel'),
                  result: _lastResult!.vowelTask,
                  showMore: _showMoreVowelParams,
                  onToggleShowMore: () => setState(() => _showMoreVowelParams = !_showMoreVowelParams),
                ),
                if (_lastResult!.phraseTask != null) ...[
                  const SizedBox(height: 28),
                  _buildTaskDetailSection(
                    taskLabel: _s('phraseTaskLabel'),
                    result: _lastResult!.phraseTask!,
                    showMore: _showMorePhraseParams,
                    onToggleShowMore: () => setState(() => _showMorePhraseParams = !_showMorePhraseParams),
                  ),
                ],
              ],
            ],
          ),
        ),
      ),
      ),
      ),
    );
  }
}

class _GaugePainter extends CustomPainter {
  final double value; // 0.0 - 1.0
  final Color color;

  const _GaugePainter({required this.value, required this.color});

  static const double _strokeWidth = 14;
  static const double _startAngle = math.pi; // 9 o'clock
  static const double _sweep = math.pi; // half circle, through 12 to 3 o'clock

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromLTWH(
      _strokeWidth / 2,
      _strokeWidth / 2,
      size.width - _strokeWidth,
      size.width - _strokeWidth,
    );

    final track = Paint()
      ..color = _stroke
      ..strokeWidth = _strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, _startAngle, _sweep, false, track);

    final progress = Paint()
      ..color = color
      ..strokeWidth = _strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, _startAngle, _sweep * value.clamp(0.0, 1.0), false, progress);
  }

  @override
  bool shouldRepaint(covariant _GaugePainter oldDelegate) =>
      oldDelegate.value != value || oldDelegate.color != color;
}
