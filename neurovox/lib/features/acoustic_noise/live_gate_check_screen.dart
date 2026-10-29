// Component 1 - Live Mic Test: "Audio Quality Check".
//
// Shows what the quality gate does with one take, on its own (no Component 2/3):
//   pick a task -> record 5 s -> decision + score + message
//   -> how the gate decided (each check vs its threshold)
//   -> what enhancement did (forwarded audio, biomarker change vs tolerance)
//   -> waveform / spectrogram plots (raw above enhanced)
//   -> list of the takes checked in this session.
//
// Calls QualityGateApiService directly (not QualityGate.check) so FAIL reports
// are shown in full instead of being thrown away.

import 'dart:async';

import 'package:flutter/material.dart';

import 'gate_colors.dart';
import 'models/quality_report.dart';
import 'services/quality_gate_api_service.dart';
import 'take_recorder.dart';

enum _Phase { idle, recording, checking }

/// One row of "How the gate decided".
class _Check {
  final String label;
  final String measured;
  final String rule;
  final bool? passed; // null = not measured
  final Widget? extra;

  const _Check(this.label, this.measured, this.rule, this.passed, {this.extra});
}

class LiveGateCheckScreen extends StatefulWidget {
  const LiveGateCheckScreen({super.key});

  @override
  State<LiveGateCheckScreen> createState() => _LiveGateCheckScreenState();
}

class _LiveGateCheckScreenState extends State<LiveGateCheckScreen> {
  final TakeRecorder _takeRecorder = TakeRecorder();
  StreamSubscription<double>? _levelSub;

  QualityTask _task = QualityTask.vowel;
  _Phase _phase = _Phase.idle;
  int _remaining = takeSeconds;
  double _levelDbfs = -160;

  GateThresholds? _thresholds;
  String? _thresholdsError;
  QualityReport? _report;
  String? _error;
  final List<QualityReport> _history = [];

  @override
  void initState() {
    super.initState();
    _loadThresholds();
  }

  @override
  void dispose() {
    _levelSub?.cancel();
    _takeRecorder.dispose();
    super.dispose();
  }

  Future<void> _loadThresholds() async {
    try {
      final thresholds = await QualityGateApiService.fetchThresholds();
      if (mounted) {
        setState(() {
          _thresholds = thresholds;
          _thresholdsError = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _thresholdsError = e.toString());
    }
  }

  Future<void> _startRecording() async {
    setState(() {
      _error = null;
      _report = null;
      _remaining = takeSeconds;
    });
    try {
      await _takeRecorder.start(
        name: 'live_${_task.apiValue}',
        onTick: (left) {
          if (mounted) setState(() => _remaining = left);
        },
        onTimeUp: _stopAndCheck,
      );
    } catch (e) {
      setState(() => _error = e.toString());
      return;
    }
    _levelSub?.cancel();
    _levelSub = _takeRecorder.levels().listen((db) {
      if (mounted) setState(() => _levelDbfs = db);
    });
    setState(() => _phase = _Phase.recording);
  }

  Future<void> _stopAndCheck() async {
    if (_phase != _Phase.recording) return;
    await _levelSub?.cancel();
    _levelSub = null;
    setState(() {
      _phase = _Phase.checking;
      _levelDbfs = -160;
    });

    String? filePath;
    try {
      final take = await _takeRecorder.stop();
      filePath = take.filePath;
      final report = await QualityGateApiService.check(
        task: _task,
        filePath: take.filePath,
        bytes: take.bytes,
        filename: 'live_${_task.apiValue}.wav',
      );
      if (!mounted) return;
      setState(() {
        _report = report;
        _history.insert(0, report);
      });
      if (_thresholds == null) _loadThresholds();
    } on QualityGateRejected catch (e) {
      // 422: the audio could not be decoded at all.
      if (mounted) setState(() => _report = e.report);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      await TakeRecorder.deleteFile(filePath);
      if (mounted) setState(() => _phase = _Phase.idle);
    }
  }

  // ---------------------------------------------------------------- build

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: GateColors.bg,
      appBar: AppBar(
        backgroundColor: GateColors.bg,
        foregroundColor: GateColors.textPrimary,
        elevation: 0,
        title: const Text('Audio Quality Check', style: TextStyle(fontWeight: FontWeight.w600)),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            _serverStatus(),
            const SizedBox(height: 12),
            _recorderCard(),
            if (_error != null) ...[
              const SizedBox(height: 12),
              _messageCard(_error!, GateColors.danger, Icons.error_outline_rounded),
            ],
            if (_report != null) ...[
              const SizedBox(height: 16),
              _decisionBanner(_report!),
              if (_report!.clipId.isNotEmpty) ...[
                const SizedBox(height: 16),
                _section('How the gate decided', _checksList(_report!)),
              ],
              if (_report!.qualityBefore != null) ...[
                const SizedBox(height: 16),
                _section('Enhancement', _enhancement(_report!)),
                const SizedBox(height: 16),
                _section('Waveform & spectrogram (top: raw, bottom: enhanced)', _plots(_report!)),
              ],
            ],
            if (_history.isNotEmpty) ...[
              const SizedBox(height: 16),
              _section('This session', _historyList()),
            ],
          ],
        ),
      ),
    );
  }

  Widget _serverStatus() {
    final t = _thresholds;
    if (t != null) {
      return Text(
        'Gate ${t.gateModel} · config v${t.configVersion} · enhancement ${t.enhancementMethod}',
        style: const TextStyle(color: GateColors.textFaint, fontSize: 12),
      );
    }
    if (_thresholdsError != null) {
      return Row(children: [
        Expanded(child: _messageCard(_thresholdsError!, GateColors.warn, Icons.cloud_off_rounded)),
        IconButton(
          onPressed: _loadThresholds,
          icon: const Icon(Icons.refresh_rounded, color: GateColors.textSecondary),
          tooltip: 'Retry',
        ),
      ]);
    }
    return const Text('Connecting to the quality gate...', style: TextStyle(color: GateColors.textFaint, fontSize: 12));
  }

  Widget _recorderCard() {
    final bool idle = _phase == _Phase.idle;
    final bool recording = _phase == _Phase.recording;
    final String prompt = _task == QualityTask.vowel
        ? 'Say "aaaa" in one steady sound until the timer ends.'
        : 'Repeat "pa-ta-ka" quickly and clearly until the timer ends.';

    return _card(
      Column(children: [
        SegmentedButton<QualityTask>(
          segments: const [
            ButtonSegment(value: QualityTask.vowel, label: Text('Vowel "aaaa"')),
            ButtonSegment(value: QualityTask.ddk, label: Text('DDK "pa-ta-ka"')),
          ],
          selected: {_task},
          onSelectionChanged: idle ? (s) => setState(() => _task = s.first) : null,
          style: ButtonStyle(
            foregroundColor: WidgetStateProperty.resolveWith(
                (s) => s.contains(WidgetState.selected) ? GateColors.bg : GateColors.textSecondary),
            backgroundColor: WidgetStateProperty.resolveWith(
                (s) => s.contains(WidgetState.selected) ? GateColors.accent : Colors.transparent),
            side: WidgetStateProperty.all(const BorderSide(color: GateColors.stroke)),
          ),
        ),
        const SizedBox(height: 16),
        Text(prompt, textAlign: TextAlign.center, style: const TextStyle(color: GateColors.textSecondary)),
        const SizedBox(height: 20),
        GestureDetector(
          onTap: idle ? _startRecording : null,
          child: Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: recording ? GateColors.danger : (idle ? GateColors.accent : GateColors.surfaceRaised),
            ),
            alignment: Alignment.center,
            child: switch (_phase) {
              _Phase.idle => const Icon(Icons.mic_rounded, size: 44, color: GateColors.bg),
              _Phase.recording => Text('$_remaining',
                  style: const TextStyle(fontSize: 40, fontWeight: FontWeight.w700, color: GateColors.textPrimary)),
              _Phase.checking => const SizedBox(
                  width: 36, height: 36, child: CircularProgressIndicator(color: GateColors.accent, strokeWidth: 3)),
            },
          ),
        ),
        const SizedBox(height: 12),
        Text(
          switch (_phase) {
            _Phase.idle => 'Tap to record $takeSeconds s',
            _Phase.recording => 'Recording...',
            _Phase.checking => 'Checking quality...',
          },
          style: const TextStyle(color: GateColors.textFaint, fontSize: 12),
        ),
        const SizedBox(height: 16),
        _levelMeter(),
      ]),
    );
  }

  /// Live microphone level, -60 dBFS (empty) to 0 dBFS (full).
  Widget _levelMeter() {
    final double fraction = ((_levelDbfs + 60) / 60).clamp(0.0, 1.0);
    final Color color = _levelDbfs > -3 ? GateColors.danger : (_levelDbfs > -12 ? GateColors.warn : GateColors.accent);
    return Row(children: [
      const Icon(Icons.graphic_eq_rounded, size: 16, color: GateColors.textFaint),
      const SizedBox(width: 8),
      Expanded(
        child: ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: _phase == _Phase.recording ? fraction : 0,
            minHeight: 8,
            backgroundColor: GateColors.surfaceRaised,
            valueColor: AlwaysStoppedAnimation(color),
          ),
        ),
      ),
      const SizedBox(width: 8),
      SizedBox(
        width: 70,
        child: Text(
          _phase == _Phase.recording ? '${_levelDbfs.toStringAsFixed(0)} dBFS' : '-- dBFS',
          textAlign: TextAlign.right,
          style: const TextStyle(color: GateColors.textFaint, fontSize: 12),
        ),
      ),
    ]);
  }

  Widget _decisionBanner(QualityReport r) {
    final Color color = r.passed ? GateColors.accent : GateColors.danger;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.6)),
      ),
      child: Row(children: [
        Icon(r.passed ? Icons.check_circle_rounded : Icons.cancel_rounded, color: color, size: 40),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(
              '${r.decision}  ·  score ${r.qualityScore.toStringAsFixed(0)}/100',
              style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(r.userMessage, style: const TextStyle(color: GateColors.textPrimary)),
            const SizedBox(height: 4),
            Text('reason: ${r.reason}', style: const TextStyle(color: GateColors.textFaint, fontSize: 12)),
          ]),
        ),
      ]),
    );
  }

  List<_Check> _checks(QualityReport r) {
    final t = _thresholds;
    final q = r.judgedQuality;
    final v = r.voiceCheck;
    final String which = r.featuresPreserved == true ? 'enhanced' : 'raw';

    String fmt(double? x, String unit, [int digits = 1]) => x == null ? '--' : '${x.toStringAsFixed(digits)}$unit';

    final double d = r.durationSeconds;
    final checks = <_Check>[
      _Check(
        'Length',
        fmt(d, ' s', 2),
        t == null ? '' : '${fmt(t.minDurationS, '')}-${fmt(t.maxDurationS, ' s')}',
        t == null ? null : d >= t.minDurationS && d <= t.maxDurationS,
      ),
    ];
    if (q == null) return checks; // failed the length check: nothing else was measured

    checks.addAll([
      _Check(
        'Clipping ($which)',
        fmt(q.clippingPct, ' %', 2),
        t == null ? '' : '≤ ${fmt(t.maxClippingPct, ' %')}',
        t == null || q.clippingPct == null ? null : q.clippingPct! <= t.maxClippingPct,
      ),
      _Check(
        'Voice activity ($which)',
        fmt(q.voiceActivityPct, ' %'),
        t == null ? '' : '≥ ${fmt(t.minVoiceActivityPct, ' %')}',
        t == null || q.voiceActivityPct == null ? null : q.voiceActivityPct! >= t.minVoiceActivityPct,
      ),
      _Check(
        'Speech contrast ($which)',
        fmt(q.speechBandContrastDb, ' dB'),
        t == null ? '' : '≥ ${fmt(t.passContrastDb, ' dB')}',
        t == null || q.speechBandContrastDb == null ? null : q.speechBandContrastDb! >= t.passContrastDb,
        extra: t == null || q.speechBandContrastDb == null ? null : _contrastBar(q.speechBandContrastDb!, t),
      ),
    ]);
    if (v != null) {
      checks.add(_Check(
        'Voice present (raw)',
        '${fmt(v.speechBandContrastDb, ' dB')}, ${fmt(v.levelDbfs, ' dBFS')}',
        t == null
            ? ''
            : 'contrast ≥ ${fmt(t.minContrastDb, ' dB')}, or level > ${fmt(t.noVoiceMaxLevelDbfs, ' dBFS')}',
        v.passed,
      ));
    }
    return checks;
  }

  Widget _checksList(QualityReport r) {
    final checks = _checks(r);
    final int firstFail = checks.indexWhere((c) => c.passed == false);
    return Column(children: [
      for (int i = 0; i < checks.length; i++) _checkRow(checks[i], decidedHere: i == firstFail && !r.passed),
      if (_thresholds == null)
        const Padding(
          padding: EdgeInsets.only(top: 8),
          child: Text('Thresholds unavailable (could not read /health).',
              style: TextStyle(color: GateColors.textFaint, fontSize: 12)),
        ),
    ]);
  }

  Widget _checkRow(_Check c, {required bool decidedHere}) {
    final Color color = c.passed == null ? GateColors.textFaint : (c.passed! ? GateColors.accent : GateColors.danger);
    final IconData icon = c.passed == null
        ? Icons.remove_circle_outline_rounded
        : (c.passed! ? Icons.check_circle_outline_rounded : Icons.highlight_off_rounded);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: GateColors.surfaceRaised,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: decidedHere ? GateColors.danger : GateColors.stroke),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(c.label, style: const TextStyle(color: GateColors.textPrimary, fontWeight: FontWeight.w600))),
          Text(c.measured, style: TextStyle(color: color, fontWeight: FontWeight.w600)),
        ]),
        if (c.rule.isNotEmpty || decidedHere)
          Padding(
            padding: const EdgeInsets.only(left: 30, top: 4),
            child: Text(
              [if (c.rule.isNotEmpty) 'needs ${c.rule}', if (decidedHere) 'decided here'].join('  ·  '),
              style: TextStyle(color: decidedHere ? GateColors.danger : GateColors.textFaint, fontSize: 12),
            ),
          ),
        if (c.extra != null) Padding(padding: const EdgeInsets.only(left: 30, top: 8), child: c.extra!),
      ]),
    );
  }

  /// 0-20 dB bar with marks at the no-voice limit and the pass threshold.
  Widget _contrastBar(double value, GateThresholds t) {
    const double maxDb = 20;
    double pos(double db) => (db / maxDb).clamp(0.0, 1.0);
    final Color color = value >= t.passContrastDb ? GateColors.accent : (value >= t.minContrastDb ? GateColors.warn : GateColors.danger);
    return LayoutBuilder(builder: (context, box) {
      final double w = box.maxWidth;
      Widget mark(double db, String label) => Positioned(
            left: (pos(db) * w - 1).clamp(0.0, w - 2),
            top: 0,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(width: 2, height: 14, color: GateColors.textSecondary),
              Text(label, style: const TextStyle(color: GateColors.textFaint, fontSize: 10)),
            ]),
          );
      return SizedBox(
        height: 32,
        child: Stack(children: [
          Positioned(
            left: 0,
            right: 0,
            top: 3,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: pos(value),
                minHeight: 8,
                backgroundColor: GateColors.bg,
                valueColor: AlwaysStoppedAnimation(color),
              ),
            ),
          ),
          mark(t.minContrastDb, '${t.minContrastDb.toStringAsFixed(0)} flat'),
          mark(t.passContrastDb, '${t.passContrastDb.toStringAsFixed(0)} pass'),
        ]),
      );
    });
  }

  Widget _enhancement(QualityReport r) {
    final tolerances = _thresholds?.featureTolerances[r.task] ?? const <String, double?>{};
    final String forwarded = !r.passed
        ? 'Nothing forwarded (recording rejected)'
        : r.audioChoice == 'enhanced'
            ? 'Enhanced audio forwarded'
            : 'Raw audio forwarded (enhancement changed the biomarkers too much)';
    final String preserved = switch (r.featuresPreserved) {
      true => 'Enhancement kept every biomarker within tolerance.',
      false => 'Enhancement changed a biomarker beyond tolerance, so the gate judged the raw audio.',
      null => '',
    };

    String fmt(double? x) => x == null ? '--' : (x.abs() >= 100 ? x.toStringAsFixed(0) : x.toStringAsFixed(3));

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(forwarded, style: TextStyle(color: r.passed ? GateColors.accent : GateColors.textSecondary, fontWeight: FontWeight.w600)),
      if (preserved.isNotEmpty) ...[
        const SizedBox(height: 4),
        Text(preserved, style: const TextStyle(color: GateColors.textSecondary, fontSize: 13)),
      ],
      if (r.featureChange.isNotEmpty) ...[
        const SizedBox(height: 12),
        const Row(children: [
          Expanded(flex: 4, child: Text('Biomarker', style: TextStyle(color: GateColors.textFaint, fontSize: 12))),
          Expanded(flex: 5, child: Text('raw → enhanced', style: TextStyle(color: GateColors.textFaint, fontSize: 12))),
          Expanded(
              flex: 3,
              child: Text('change', textAlign: TextAlign.right, style: TextStyle(color: GateColors.textFaint, fontSize: 12))),
        ]),
        const Divider(color: GateColors.stroke, height: 12),
        for (final name in r.featureChange.keys)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Builder(builder: (context) {
              final double? change = r.featureChange[name];
              final double? tol = tolerances[name];
              final bool? ok = change == null || tol == null ? null : change.abs() <= tol;
              final Color color = ok == null ? GateColors.textSecondary : (ok ? GateColors.accent : GateColors.danger);
              String pct(double? x) => x == null ? '--' : '${(x * 100).toStringAsFixed(1)}%';
              return Row(children: [
                Expanded(flex: 4, child: Text(name, style: const TextStyle(color: GateColors.textPrimary, fontSize: 13))),
                Expanded(
                  flex: 5,
                  child: Text('${fmt(r.featuresBefore[name])} → ${fmt(r.featuresAfter[name])}',
                      style: const TextStyle(color: GateColors.textSecondary, fontSize: 13)),
                ),
                Expanded(
                  flex: 3,
                  child: Text(
                    tol == null ? pct(change) : '${pct(change)} / ${pct(tol)}',
                    textAlign: TextAlign.right,
                    style: TextStyle(color: color, fontSize: 13),
                  ),
                ),
              ]);
            }),
          ),
      ],
    ]);
  }

  Widget _plots(QualityReport r) {
    Widget plot(String name) => ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Container(
            color: Colors.white,
            child: Image.network(
              QualityGateApiService.plotUrl(r.clipId, name),
              fit: BoxFit.contain,
              loadingBuilder: (context, child, progress) => progress == null
                  ? child
                  : const SizedBox(height: 160, child: Center(child: CircularProgressIndicator(color: GateColors.accent))),
              errorBuilder: (context, error, stack) => Container(
                height: 80,
                color: GateColors.surfaceRaised,
                alignment: Alignment.center,
                child: Text('Could not load $name', style: const TextStyle(color: GateColors.textFaint)),
              ),
            ),
          ),
        );
    return Column(children: [plot('waveform.png'), const SizedBox(height: 12), plot('spectrogram.png')]);
  }

  Widget _historyList() {
    return Column(children: [
      for (int i = 0; i < _history.length; i++)
        Builder(builder: (context) {
          final r = _history[i];
          final Color color = r.passed ? GateColors.accent : GateColors.danger;
          final double? contrast = r.judgedQuality?.speechBandContrastDb;
          return ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            onTap: () => setState(() => _report = r),
            leading: Icon(r.passed ? Icons.check_circle_rounded : Icons.cancel_rounded, color: color),
            title: Text(
              '#${_history.length - i}  ${r.task}  ·  ${r.decision}  ·  ${r.qualityScore.toStringAsFixed(0)}',
              style: const TextStyle(color: GateColors.textPrimary),
            ),
            subtitle: Text(
              '${r.reason}  ·  ${r.durationSeconds.toStringAsFixed(2)} s'
              '${contrast == null ? '' : '  ·  contrast ${contrast.toStringAsFixed(1)} dB'}',
              style: const TextStyle(color: GateColors.textFaint, fontSize: 12),
            ),
            trailing: identical(r, _report) ? const Icon(Icons.visibility_rounded, color: GateColors.textFaint, size: 18) : null,
          );
        }),
      const Text('Tap a take to show its report again.', style: TextStyle(color: GateColors.textFaint, fontSize: 11)),
    ]);
  }

  // ---------------------------------------------------------------- helpers

  Widget _section(String title, Widget child) => _card(Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(color: GateColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          child,
        ],
      ));

  Widget _card(Widget child) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: GateColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: GateColors.stroke),
        ),
        child: child,
      );

  Widget _messageCard(String text, Color color, IconData icon) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.5)),
        ),
        child: Row(children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: TextStyle(color: color, fontSize: 13))),
        ]),
      );
}
