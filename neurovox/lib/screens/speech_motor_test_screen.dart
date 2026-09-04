import 'dart:async';
import 'package:flutter/material.dart';

class SpeechMotorTestScreen extends StatefulWidget {
  const SpeechMotorTestScreen({super.key});

  @override
  State<SpeechMotorTestScreen> createState() => _SpeechMotorTestScreenState();
}

class _SpeechMotorTestScreenState extends State<SpeechMotorTestScreen> {
  bool _isRecording = false;
  int _secondsRemaining = 10;
  Timer? _timer;

  void _startRecording() {
    setState(() {
      _isRecording = true;
      _secondsRemaining = 10;
    });

    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_secondsRemaining > 0) {
        setState(() {
          _secondsRemaining--;
        });
      } else {
        _stopRecording();
        _showSuccessDialog();
      }
    });
  }

  void _stopRecording() {
    _timer?.cancel();
    setState(() {
      _isRecording = false;
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _showSuccessDialog() {
    const Color primaryBlue = Color(0xFF2563EB);

    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
          backgroundColor: Colors.white,
          title: const Row(
            children: [
              Icon(Icons.check_circle_rounded, color: primaryBlue, size: 28),
              SizedBox(width: 10),
              Text(
                'Task Complete',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Your speech-motor coordination data has been processed.',
                style: TextStyle(color: Color(0xFF4A4A4A), fontSize: 14),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFFEFF6FF),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'DDK Rate (Syllables/sec):',
                      style: TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF2D3748)),
                    ),
                    Text(
                      '6.2 (Normal)',
                      style: TextStyle(fontWeight: FontWeight.w800, color: primaryBlue),
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
                style: TextStyle(color: primaryBlue, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildInstructionCard(String step, String title, String description, IconData icon) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF2563EB).withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFEFF6FF),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: const Color(0xFF2563EB), size: 24),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$step: $title',
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 15,
                    color: Color(0xFF1E293B),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  description,
                  style: const TextStyle(
                    fontSize: 13,
                    color: Color(0xFF64748B),
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    const Color primaryBlue = Color(0xFF2563EB);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Speech-Motor Test',
            style: TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Articulatory coordination & DDK syllable repetition',
            style: TextStyle(fontSize: 14, color: mediumGrey, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 24),

          // Main Test Card
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: primaryBlue.withValues(alpha: 0.08),
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
                  decoration: BoxDecoration(
                    color: _isRecording ? Colors.redAccent.withValues(alpha: 0.1) : const Color(0xFFEFF6FF),
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Icon(
                      _isRecording ? Icons.mic_rounded : Icons.settings_voice_rounded,
                      size: 48,
                      color: _isRecording ? Colors.redAccent : primaryBlue,
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  _isRecording ? '$_secondsRemaining Seconds Left' : 'Diadochokinetic (DDK) Rate',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: _isRecording ? Colors.redAccent : darkSlate,
                  ),
                ),
                const SizedBox(height: 10),
                const Text(
                  'Repeat "PA-TA-KA" rapidly',
                  style: TextStyle(color: mediumGrey, fontSize: 14, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 24),

                if (_isRecording)
                  Column(
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: LinearProgressIndicator(
                          value: 1.0 - (_secondsRemaining / 10.0),
                          minHeight: 10,
                          backgroundColor: Colors.grey.shade200,
                          valueColor: const AlwaysStoppedAnimation<Color>(Colors.redAccent),
                        ),
                      ),
                      const SizedBox(height: 24),
                    ],
                  ),

                ElevatedButton(
                  onPressed: _isRecording ? _stopRecording : _startRecording,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isRecording ? Colors.redAccent : primaryBlue,
                    minimumSize: const Size(double.infinity, 54),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                  child: Text(
                    _isRecording ? 'Stop Recording' : 'Start DDK Speech Task',
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          const Text(
            'How to perform the test',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 14),

          _buildInstructionCard(
            'Step 1',
            'Prepare',
            'Sit in a quiet room, hold the phone 6 inches from your mouth, and take a deep breath.',
            Icons.nature_people_outlined,
          ),
          _buildInstructionCard(
            'Step 2',
            'Repeat',
            'When you tap start, repeat the syllables "PA-TA-KA" as fast and evenly as possible.',
            Icons.record_voice_over_outlined,
          ),
          _buildInstructionCard(
            'Step 3',
            'Maintain',
            'Keep an even cadence for the full 10 seconds. The test will automatically stop.',
            Icons.timer_outlined,
          ),
        ],
      ),
    );
  }
}
