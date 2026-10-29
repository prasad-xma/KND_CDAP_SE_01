
library;

enum RiskTier { low, moderate, high }

class FusionResult {
  final double fusedProbabilityPd;
  final RiskTier tier;
  final bool concordant;

  const FusionResult({
    required this.fusedProbabilityPd,
    required this.tier,
    required this.concordant,
  });
}

class RiskFusion {
  // Reliability weights: each modality's own validated balanced accuracy,
  // same idea as the "weighted_ensemble" strategy in
  // fusion/train_italian_pvs_fusion.py (weight by how trustworthy that
  // modality's model actually is, not a fixed 50/50 split). Motor's weight
  // is low while it only produces a placeholder value.
  static const double phonationWeight = 0.7;
  static const double motorWeight = 0.3;

  static const double lowRiskCutoff = 0.35;
  static const double highRiskCutoff = 0.65;

  static FusionResult compute({
    required double phonationProbabilityPd,
    required double motorProbabilityPd,
  }) {
    final double weightSum = phonationWeight + motorWeight;
    final double fused =
        (phonationWeight * phonationProbabilityPd + motorWeight * motorProbabilityPd) / weightSum;

    final RiskTier tier = fused < lowRiskCutoff
        ? RiskTier.low
        : (fused > highRiskCutoff ? RiskTier.high : RiskTier.moderate);

    final bool concordant = (phonationProbabilityPd >= 0.5) == (motorProbabilityPd >= 0.5);

    return FusionResult(fusedProbabilityPd: fused, tier: tier, concordant: concordant);
  }
}
