import 'package:flutter/material.dart';
import '../core/i18n/language_controller.dart';
import '../core/widgets/language_toggle_button.dart';

class SpeechMotorTestScreen extends StatefulWidget {
  final VoidCallback? onClose;

  const SpeechMotorTestScreen({super.key, this.onClose});

  @override
  State<SpeechMotorTestScreen> createState() => _SpeechMotorTestScreenState();
}

class _SpeechMotorTestScreenState extends State<SpeechMotorTestScreen> {
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

    return ListenableBuilder(
      listenable: LanguageController.instance,
      builder: (context, _) {
        return SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                crossAxisAlignment: CrossAxisAlignment.start,
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
                            letterSpacing: -0.5,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          tr('motorSubtitle'),
                          style: const TextStyle(fontSize: 14, color: mediumGrey, fontWeight: FontWeight.w500),
                        ),
                      ],
                    ),
                  ),
                  const LanguageToggleButton(activeColor: primaryBlue),
                  if (widget.onClose != null)
                    IconButton(
                      onPressed: widget.onClose,
                      icon: const Icon(Icons.close_rounded, color: mediumGrey),
                    ),
                ],
              ),
              const SizedBox(height: 24),

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
                      decoration: const BoxDecoration(
                        color: Color(0xFFEFF6FF),
                        shape: BoxShape.circle,
                      ),
                      child: const Center(
                        child: Icon(Icons.construction_rounded, size: 44, color: primaryBlue),
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      tr('notAvailableYetTitle'),
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                        color: darkSlate,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      tr('motorNotAvailableDesc'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: mediumGrey, fontSize: 14, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              Text(
                tr('howToPerformTest'),
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: darkSlate,
                  letterSpacing: -0.3,
                ),
              ),
              const SizedBox(height: 14),

              _buildInstructionCard(
                '1',
                tr('step1TitleMotor'),
                tr('step1DescMotor'),
                Icons.nature_people_outlined,
              ),
              _buildInstructionCard(
                '2',
                tr('step2TitleMotor'),
                tr('step2DescMotor'),
                Icons.record_voice_over_outlined,
              ),
              _buildInstructionCard(
                '3',
                tr('step3TitleMotor'),
                tr('step3DescMotor'),
                Icons.timer_outlined,
              ),
            ],
          ),
        );
      },
    );
  }
}
