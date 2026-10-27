import 'package:flutter/material.dart';
import '../core/i18n/language_controller.dart';

class LiveMicTestScreen extends StatelessWidget {
  const LiveMicTestScreen({super.key});

  @override
  Widget build(BuildContext context) {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return ListenableBuilder(
      listenable: LanguageController.instance,
      builder: (context, _) => Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: darkSlate,
        title: Text(
          tr('liveMicTestTitle'),
          style: const TextStyle(fontWeight: FontWeight.w800, color: darkSlate),
        ),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: const BoxDecoration(
                  color: Color(0xFFE6F8F5),
                  shape: BoxShape.circle,
                ),
                child: const Center(
                  child: Icon(Icons.construction_rounded, size: 40, color: primaryTeal),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                tr('notAvailableYetTitle'),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: darkSlate),
              ),
              const SizedBox(height: 8),
              Text(
                tr('liveMicNotAvailableDesc'),
                textAlign: TextAlign.center,
                style: const TextStyle(color: mediumGrey, fontSize: 13.5, fontWeight: FontWeight.w500),
              ),
            ],
          ),
        ),
      ),
      ),
    );
  }
}
