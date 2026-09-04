import 'dart:math' as math;
import 'package:flutter/material.dart';

class PhonationTestScreen extends StatefulWidget {
  const PhonationTestScreen({super.key});

  @override
  State<PhonationTestScreen> createState() => _PhonationTestScreenState();
}

class _PhonationTestScreenState extends State<PhonationTestScreen> with SingleTickerProviderStateMixin {
  bool _isRecordingSimulated = false;
  late final AnimationController _pulseController;

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
    super.dispose();
  }

  void _showRecordVoiceModal() {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color primaryTealLight = Color(0xFF0EC4B7);
    const Color darkGrey = Color(0xFF2D3748);
    const Color lightGrey = Color(0xFF718096);

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
                      const Text(
                        'Vocal Biomarker Check',
                        style: TextStyle(
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
                  const Text(
                    'Please pronounce a steady sustained vowel /a/ into the microphone for 5 seconds.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
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
                        final double barHeight = _isRecordingSimulated
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
                    _isRecordingSimulated ? 'Listening & Analyzing Frequency...' : 'Ready to record',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: _isRecordingSimulated ? primaryTeal : lightGrey,
                    ),
                  ),
                  const Spacer(),
                  GestureDetector(
                    onTap: () {
                      setModalState(() {
                        _isRecordingSimulated = !_isRecordingSimulated;
                      });
                      setState(() {});

                      if (_isRecordingSimulated) {
                        Future.delayed(const Duration(seconds: 4), () {
                          if (modalContext.mounted) {
                            Navigator.pop(modalContext);
                            _showSuccessAssessmentDialog();
                          }
                          setState(() {
                            _isRecordingSimulated = false;
                          });
                        });
                      }
                    },
                    child: Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: LinearGradient(
                          colors: _isRecordingSimulated
                              ? [Colors.redAccent, Colors.red]
                              : [primaryTealLight, primaryTeal],
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: (_isRecordingSimulated ? Colors.red : primaryTeal).withValues(alpha: 0.4),
                            blurRadius: 24,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      child: Icon(
                        _isRecordingSimulated ? Icons.stop_rounded : Icons.mic_rounded,
                        color: Colors.white,
                        size: 38,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    _isRecordingSimulated ? 'Tap to cancel' : 'Tap mic to start test',
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

  void _showSuccessAssessmentDialog() {
    const Color primaryTeal = Color(0xFF0C9388);

    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
          backgroundColor: Colors.white,
          title: const Row(
            children: [
              Icon(Icons.check_circle_rounded, color: primaryTeal, size: 28),
              SizedBox(width: 10),
              Text(
                'Analysis Complete',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Your vocal biomarkers have been processed successfully.',
                style: TextStyle(color: Color(0xFF4A4A4A), fontSize: 14),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFFD6ECE6).withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Voice Stability Score:',
                      style: TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF2D3748)),
                    ),
                    Text(
                      '96% (Optimal)',
                      style: TextStyle(fontWeight: FontWeight.w800, color: primaryTeal),
                    ),
                  ],
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text(
                'View Detailed Report',
                style: TextStyle(color: primaryTeal, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildMetricRow(String label, String value, String status) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF2D3748), fontSize: 13)),
          Row(
            children: [
              Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF0C9388), fontSize: 13)),
              const SizedBox(width: 8),
              Text('($status)', style: const TextStyle(fontSize: 11, color: Color(0xFF64748B))),
            ],
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
            'Phonation Test',
            style: TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Sustained vowel acoustic biomarker assessment',
            style: TextStyle(fontSize: 14, color: mediumGrey, fontWeight: FontWeight.w500),
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
                const Text(
                  'Sustained /a/ Vowel Task',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: darkSlate),
                ),
                const SizedBox(height: 10),
                const Text(
                  'Take a deep breath and vocalize a steady "/a/" sound into the microphone for 5 continuous seconds at a comfortable pitch.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 14, color: mediumGrey, height: 1.5),
                ),
                const SizedBox(height: 24),
                ElevatedButton.icon(
                  onPressed: _showRecordVoiceModal,
                  icon: const Icon(Icons.play_arrow_rounded, color: Colors.white),
                  label: const Text(
                    'Begin Phonation Task',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
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

          // Diagnostic Metrics Preview
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
                const Text('Extracted Acoustic Parameters', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 14),
                _buildMetricRow('Fundamental Freq (F0)', '124.5 Hz', 'Optimal'),
                const Divider(),
                _buildMetricRow('Jitter (local)', '0.34%', 'Normal (< 1.0%)'),
                const Divider(),
                _buildMetricRow('Shimmer (apq3)', '1.82%', 'Normal (< 3.0%)'),
                const Divider(),
                _buildMetricRow('Harmonics-to-Noise (HNR)', '22.4 dB', 'Good (> 20 dB)'),
              ],
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }
}
