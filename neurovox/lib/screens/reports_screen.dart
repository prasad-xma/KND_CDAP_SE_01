import 'package:flutter/material.dart';

class ReportsScreen extends StatefulWidget {
  const ReportsScreen({super.key});

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _animationController;
  late final Animation<double> _scoreAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    );
    _scoreAnimation = Tween<double>(begin: 0.0, end: 94.2).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeOutCubic),
    );
    _animationController.forward();
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  Widget _buildMetricCard(String title, String value, String unit, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.08),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 28),
          const Spacer(),
          Text(
            title,
            style: const TextStyle(fontSize: 13, color: Color(0xFF64748B), fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                value,
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: color),
              ),
              const SizedBox(width: 4),
              Text(
                unit,
                style: const TextStyle(fontSize: 12, color: Color(0xFF64748B), fontWeight: FontWeight.w600),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHistoryItem(String date, String score, bool isImprovement) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: isImprovement ? const Color(0xFFD6ECE6) : const Color(0xFFFEF3C7),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  isImprovement ? Icons.trending_up_rounded : Icons.trending_down_rounded,
                  color: isImprovement ? const Color(0xFF0C9388) : const Color(0xFFD97706),
                  size: 16,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                date,
                style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF1E293B), fontSize: 14),
              ),
            ],
          ),
          Text(
            score,
            style: const TextStyle(fontWeight: FontWeight.w800, color: Color(0xFF4A4A4A), fontSize: 14),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Reports & Risk Analysis',
            style: TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Multi-modal vocal biomarker fusion results',
            style: TextStyle(fontSize: 14, color: mediumGrey, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 24),

          // Main Score Card
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
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Neurological Vocal Risk', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: darkSlate)),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: const Color(0xFFE6F8F5),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Text(
                        'Low Risk',
                        style: TextStyle(color: primaryTeal, fontWeight: FontWeight.w800, fontSize: 12),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 32),
                Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox(
                      width: 160,
                      height: 160,
                      child: AnimatedBuilder(
                        animation: _scoreAnimation,
                        builder: (context, child) {
                          return CircularProgressIndicator(
                            value: _scoreAnimation.value / 100,
                            strokeWidth: 14,
                            backgroundColor: const Color(0xFFE2E8F0),
                            valueColor: const AlwaysStoppedAnimation<Color>(primaryTeal),
                            strokeCap: StrokeCap.round,
                          );
                        },
                      ),
                    ),
                    Column(
                      children: [
                        AnimatedBuilder(
                          animation: _scoreAnimation,
                          builder: (context, child) {
                            return Text(
                              '${_scoreAnimation.value.toStringAsFixed(1)}%',
                              style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w900, color: primaryTeal, height: 1.0),
                            );
                          },
                        ),
                        const SizedBox(height: 4),
                        const Text('Confidence', style: TextStyle(color: mediumGrey, fontSize: 13, fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 32),
                ElevatedButton.icon(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: const Text('Exporting Clinician PDF Report...'),
                        backgroundColor: primaryTeal,
                        behavior: SnackBarBehavior.floating,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    );
                  },
                  icon: const Icon(Icons.picture_as_pdf_outlined, color: Colors.white),
                  label: const Text('Export Clinician PDF', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: primaryTeal,
                    minimumSize: const Size(double.infinity, 54),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Detailed Metrics
          const Text(
            'Detailed Metrics',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 14),
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 2,
            crossAxisSpacing: 14,
            mainAxisSpacing: 14,
            childAspectRatio: 1.3,
            children: [
              _buildMetricCard('Jitter (Local)', '0.34', '%', Icons.graphic_eq_rounded, primaryTeal),
              _buildMetricCard('Shimmer (apq3)', '1.82', '%', Icons.waves_rounded, const Color(0xFF2563EB)),
              _buildMetricCard('HNR', '22.4', 'dB', Icons.hearing_rounded, const Color(0xFF9333EA)),
              _buildMetricCard('DDK Rate', '6.2', 'Syl/s', Icons.record_voice_over_rounded, const Color(0xFFEA580C)),
            ],
          ),
          const SizedBox(height: 24),

          // Trend History
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(24),
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
                const Text('Recent Trend', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: darkSlate)),
                const SizedBox(height: 16),
                _buildHistoryItem('Today, 10:30 AM', '94.2%', true),
                const Divider(height: 16),
                _buildHistoryItem('Sep 02, 09:15 AM', '92.8%', true),
                const Divider(height: 16),
                _buildHistoryItem('Aug 28, 02:40 PM', '89.5%', false),
                const Divider(height: 16),
                _buildHistoryItem('Aug 21, 11:00 AM', '91.2%', true),
              ],
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}
