import 'package:flutter/material.dart';
import '../i18n/language_controller.dart';

class LanguageToggleButton extends StatelessWidget {
  final Color? activeColor;
  final Color? inactiveColor;
  final Color? backgroundColor;

  const LanguageToggleButton({
    super.key,
    this.activeColor,
    this.inactiveColor,
    this.backgroundColor,
  });

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: LanguageController.instance,
      builder: (context, _) {
        final AppLanguage current = LanguageController.instance.language;
        const Color defaultTeal = Color(0xFF0C9388);
        final Color activeBg = activeColor ?? defaultTeal;
        final Color inactiveText = inactiveColor ?? const Color(0xFF718096);
        final Color bg = backgroundColor ?? Colors.white.withValues(alpha: 0.9);

        Widget pill(String label, AppLanguage lang) {
          final bool selected = current == lang;
          return GestureDetector(
            onTap: () => LanguageController.instance.setAppLanguage(lang),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: selected ? activeBg : Colors.transparent,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  color: selected ? Colors.white : inactiveText,
                ),
              ),
            ),
          );
        }

        return Container(
          height: 38,
          padding: const EdgeInsets.all(3),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: defaultTeal.withValues(alpha: 0.1),
                blurRadius: 8,
                offset: const Offset(0, 2),
              ),
            ],
            border: Border.all(color: defaultTeal.withValues(alpha: 0.15)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              pill('EN', AppLanguage.english),
              const SizedBox(width: 2),
              pill('සිං', AppLanguage.sinhala),
              const SizedBox(width: 2),
              pill('த', AppLanguage.tamil),
            ],
          ),
        );
      },
    );
  }
}
