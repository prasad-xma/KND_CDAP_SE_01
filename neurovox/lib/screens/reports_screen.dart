import 'dart:math' as math;

import 'package:flutter/material.dart';
import '../core/i18n/language_controller.dart';
import '../core/models/phonation_result.dart';
import '../core/models/speech_motor_result.dart';
import '../core/models/risk_fusion.dart';

const Color _bg = Color(0xFF0A0E14);
const Color _surfaceRaised = Color(0xFF1A2330);
const Color _stroke = Color(0xFF232E3D);
const Color _accent = Color(0xFF22E6C9);
const Color _warn = Color(0xFFFFB24B);
const Color _danger = Color(0xFFFF6B6B);
const Color _textPrimary = Color(0xFFEFF4F8);
const Color _textSecondary = Color(0xFF8C9AAE);

class ReportsScreen extends StatelessWidget {
  final PhonationDualResult? phonationResult;
  final SpeechMotorResult? speechMotorResult;

  const ReportsScreen({super.key, this.phonationResult, this.speechMotorResult});

  @override
  Widget build(BuildContext context) {
    final PhonationDualResult? r = phonationResult;
    final SpeechMotorResult? m = speechMotorResult;

    final bool hasFusedScore = r != null && m != null;
    final FusionResult? fusion = hasFusedScore
        ? RiskFusion.compute(phonationProbabilityPd: r.probabilityPd, motorProbabilityPd: m.probabilityPd)
        : null;

    final Color tierColor = switch (fusion?.tier) {
      RiskTier.low => _accent,
      RiskTier.moderate => _warn,
      RiskTier.high => _danger,
      null => _accent,
    };
    final String tierTitleKey = switch (fusion?.tier) {
      RiskTier.low => 'riskTierLowTitle',
      RiskTier.moderate => 'riskTierModerateTitle',
      RiskTier.high => 'riskTierHighTitle',
      null => 'finalScorePendingTitle',
    };
    final String tierDescKey = switch (fusion?.tier) {
      RiskTier.low => 'riskTierLowDesc',
      RiskTier.moderate => 'riskTierModerateDesc',
      RiskTier.high => 'riskTierHighDesc',
      null => 'finalScorePendingDesc',
    };

    return ListenableBuilder(
      listenable: LanguageController.instance,
      builder: (context, _) => Container(
        color: _bg,
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                tr('reportsTitle'),
                style: const TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w800,
                  color: _textPrimary,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                tr('reportsSubtitle'),
                style: const TextStyle(fontSize: 14, color: _textSecondary, fontWeight: FontWeight.w500),
              ),
              const SizedBox(height: 24),

              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: _surfaceRaised,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: _stroke),
                  boxShadow: [
                    BoxShadow(
                      color: tierColor.withValues(alpha: 0.12),
                      blurRadius: 22,
                      offset: const Offset(0, 8),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    if (hasFusedScore)
                      _buildScoreGauge(fusion!.fusedProbabilityPd, tierColor)
                    else
                      Container(
                        width: 84,
                        height: 84,
                        decoration: BoxDecoration(
                          color: _accent.withValues(alpha: 0.12),
                          shape: BoxShape.circle,
                        ),
                        child: const Center(
                          child: Icon(Icons.analytics_outlined, size: 38, color: _accent),
                        ),
                      ),
                    const SizedBox(height: 18),
                    Text(
                      tr(tierTitleKey),
                      style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: _textPrimary),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      tr(tierDescKey),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: _textSecondary, fontSize: 13.5, fontWeight: FontWeight.w500),
                    ),
                    if (hasFusedScore && !fusion!.concordant) ...[
                      const SizedBox(height: 10),
                      Text(
                        tr('fusionDiscordantNote'),
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: _warn, fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 28),

              Text(
                tr('phonationResultsSectionTitle'),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: _textPrimary, letterSpacing: -0.3),
              ),
              const SizedBox(height: 14),
              if (r == null)
                _buildEmptyCard(tr('noPhonationResultsYet'))
              else
                _buildPhonationResults(r),
              const SizedBox(height: 28),

              Text(
                tr('speechMotorResultsSectionTitle'),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: _textPrimary, letterSpacing: -0.3),
              ),
              const SizedBox(height: 14),
              if (m == null)
                _buildEmptyCard(tr('motorResultsNotAvailableDesc'))
              else
                _buildMotorResultCard(m),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildScoreGauge(double probabilityPd, Color tierColor) {
    const double size = 148;
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(
            size: const Size(size, size),
            painter: _ScoreGaugePainter(fraction: probabilityPd, color: tierColor),
          ),
          Text(
            '${(probabilityPd * 100).toStringAsFixed(0)}%',
            style: TextStyle(fontSize: 32, fontWeight: FontWeight.w800, color: tierColor),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyCard(String message) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _surfaceRaised,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _stroke),
      ),
      child: Column(
        children: [
          const Icon(Icons.hourglass_empty_rounded, color: _textSecondary, size: 24),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 12.5, color: _textSecondary, fontWeight: FontWeight.w500),
          ),
        ],
      ),
    );
  }

  Widget _buildPhonationResults(PhonationDualResult r) {
    return Column(
      children: [
        _buildTaskResultCard(
          title: tr('vowelTaskFullLabel'),
          result: r.vowelTask,
        ),
        if (r.phraseTask != null) ...[
          const SizedBox(height: 14),
          _buildTaskResultCard(
            title: tr('phraseTaskFullLabel'),
            result: r.phraseTask!,
          ),
        ],
      ],
    );
  }

  Widget _buildMotorResultCard(SpeechMotorResult m) {
    final Color accent = m.isPd ? _warn : _accent;
    final double confidence = m.isPd ? m.probabilityPd : m.probabilityHc;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: _surfaceRaised,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _stroke),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  tr('speechMotorTaskFullLabel'),
                  style: const TextStyle(fontWeight: FontWeight.bold, color: _textPrimary, fontSize: 14),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${(confidence * 100).toStringAsFixed(1)}% ${m.isPd ? "PD" : "HC"}',
                  style: TextStyle(color: accent, fontWeight: FontWeight.w800, fontSize: 12),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTaskResultCard({required String title, required PhonationResult result}) {
    final Color accent = result.isPd ? _warn : _accent;
    final double confidence = result.isPd ? result.probabilityPd : result.probabilityHc;
    final features = result.features;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: _surfaceRaised,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _stroke),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(title, style: const TextStyle(fontWeight: FontWeight.bold, color: _textPrimary, fontSize: 14)),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${(confidence * 100).toStringAsFixed(1)}% ${result.isPd ? "PD" : "HC"}',
                  style: TextStyle(color: accent, fontWeight: FontWeight.w800, fontSize: 12),
                ),
              ),
            ],
          ),
          if (features.isNotEmpty) ...[
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(child: _buildMiniMetric('F0', features['mean_f0']?.toStringAsFixed(1) ?? '-', 'Hz')),
                Expanded(child: _buildMiniMetric('Jitter', ((features['jitter'] ?? 0) * 100).toStringAsFixed(2), '%')),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(child: _buildMiniMetric('Shimmer', ((features['shimmer'] ?? 0) * 100).toStringAsFixed(2), '%')),
                Expanded(child: _buildMiniMetric('HNR', features['hnr']?.toStringAsFixed(1) ?? '-', 'dB')),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMiniMetric(String label, String value, String unit) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: _textSecondary, fontWeight: FontWeight.w600)),
        const SizedBox(height: 2),
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: _textPrimary)),
            const SizedBox(width: 3),
            Text(unit, style: const TextStyle(fontSize: 11, color: _textSecondary)),
          ],
        ),
      ],
    );
  }
}

class _ScoreGaugePainter extends CustomPainter {
  final double fraction; // 0.0 - 1.0
  final Color color;

  const _ScoreGaugePainter({required this.fraction, required this.color});

  static const double _strokeWidth = 14;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromLTWH(
      _strokeWidth / 2,
      _strokeWidth / 2,
      size.width - _strokeWidth,
      size.height - _strokeWidth,
    );

    final track = Paint()
      ..color = _stroke
      ..strokeWidth = _strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, -math.pi / 2, 2 * math.pi, false, track);

    final fillPaint = Paint()
      ..color = color
      ..strokeWidth = _strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, -math.pi / 2, 2 * math.pi * fraction.clamp(0.0, 1.0), false, fillPaint);
  }

  @override
  bool shouldRepaint(covariant _ScoreGaugePainter oldDelegate) =>
      oldDelegate.fraction != fraction || oldDelegate.color != color;
}
