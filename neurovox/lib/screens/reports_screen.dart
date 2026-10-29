import 'package:flutter/material.dart';
import '../core/i18n/language_controller.dart';
import '../core/models/phonation_result.dart';
import '../core/models/speech_motor_result.dart';
import '../core/models/risk_fusion.dart';

class ReportsScreen extends StatelessWidget {
  final PhonationDualResult? phonationResult;
  final SpeechMotorResult? speechMotorResult;

  const ReportsScreen({super.key, this.phonationResult, this.speechMotorResult});

  @override
  Widget build(BuildContext context) {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color warnOrange = Color(0xFFD97706);
    const Color dangerRed = Color(0xFFDC2626);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    final PhonationDualResult? r = phonationResult;
    final SpeechMotorResult? m = speechMotorResult;

    final bool hasFusedScore = r != null && m != null;
    final FusionResult? fusion = hasFusedScore
        ? RiskFusion.compute(phonationProbabilityPd: r.probabilityPd, motorProbabilityPd: m.probabilityPd)
        : null;

    final Color tierColor = switch (fusion?.tier) {
      RiskTier.low => primaryTeal,
      RiskTier.moderate => warnOrange,
      RiskTier.high => dangerRed,
      null => primaryTeal,
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
      builder: (context, _) => SingleChildScrollView(
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
              color: darkSlate,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            tr('reportsSubtitle'),
            style: const TextStyle(fontSize: 14, color: mediumGrey, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 24),

          Container(
            width: double.infinity,
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
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: hasFusedScore ? tierColor.withValues(alpha: 0.12) : const Color(0xFFE6F8F5),
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: hasFusedScore
                        ? Text(
                            '${(fusion!.fusedProbabilityPd * 100).toStringAsFixed(0)}%',
                            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: tierColor),
                          )
                        : const Icon(Icons.analytics_outlined, size: 36, color: primaryTeal),
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  tr(tierTitleKey),
                  style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: darkSlate),
                ),
                const SizedBox(height: 8),
                Text(
                  tr(tierDescKey),
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: mediumGrey, fontSize: 13.5, fontWeight: FontWeight.w500),
                ),
                if (hasFusedScore && !fusion!.concordant) ...[
                  const SizedBox(height: 10),
                  Text(
                    tr('fusionDiscordantNote'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: warnOrange, fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ],
                if (hasFusedScore && m.isPlaceholder) ...[
                  const SizedBox(height: 10),
                  Text(
                    tr('motorUsePlaceholderNote'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: mediumGrey, fontSize: 11.5, fontStyle: FontStyle.italic),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 28),

          Text(
            tr('phonationResultsSectionTitle'),
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: darkSlate, letterSpacing: -0.3),
          ),
          const SizedBox(height: 14),
          if (r == null)
            _buildEmptyCard(tr('noPhonationResultsYet'))
          else
            _buildPhonationResults(r),
          const SizedBox(height: 28),

          Text(
            tr('speechMotorResultsSectionTitle'),
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: darkSlate, letterSpacing: -0.3),
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
    );
  }

  Widget _buildEmptyCard(String message) {
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Column(
        children: [
          const Icon(Icons.hourglass_empty_rounded, color: mediumGrey, size: 24),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 12.5, color: darkSlate, fontWeight: FontWeight.w500),
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
        const SizedBox(height: 14),
        if (r.phraseTask != null)
          _buildTaskResultCard(
            title: tr('phraseTaskFullLabel'),
            result: r.phraseTask!,
          )
        else
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Row(
              children: [
                const Icon(Icons.info_outline_rounded, color: Color(0xFF64748B), size: 18),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    tr('phraseTaskNotRun'),
                    style: const TextStyle(fontSize: 12, color: Color(0xFF1E293B), fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildMotorResultCard(SpeechMotorResult m) {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color warnOrange = Color(0xFFD97706);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    final Color accent = m.isPd ? warnOrange : primaryTeal;
    final double confidence = m.isPd ? m.probabilityPd : m.probabilityHc;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: primaryTeal.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
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
                  style: const TextStyle(fontWeight: FontWeight.bold, color: darkSlate, fontSize: 14),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${(confidence * 100).toStringAsFixed(1)}% ${m.isPd ? "PD" : "HC"}',
                  style: TextStyle(color: accent, fontWeight: FontWeight.w800, fontSize: 12),
                ),
              ),
            ],
          ),
          if (m.isPlaceholder) ...[
            const SizedBox(height: 10),
            Text(
              tr('motorUsePlaceholderNote'),
              style: const TextStyle(fontSize: 11.5, color: mediumGrey, fontStyle: FontStyle.italic),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTaskResultCard({required String title, required PhonationResult result}) {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color warnOrange = Color(0xFFD97706);
    const Color darkSlate = Color(0xFF1E293B);

    final Color accent = result.isPd ? warnOrange : primaryTeal;
    final double confidence = result.isPd ? result.probabilityPd : result.probabilityHc;
    final features = result.features;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: primaryTeal.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(title, style: const TextStyle(fontWeight: FontWeight.bold, color: darkSlate, fontSize: 14)),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.12),
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
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: mediumGrey, fontWeight: FontWeight.w600)),
        const SizedBox(height: 2),
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: darkSlate)),
            const SizedBox(width: 3),
            Text(unit, style: const TextStyle(fontSize: 11, color: mediumGrey)),
          ],
        ),
      ],
    );
  }
}
