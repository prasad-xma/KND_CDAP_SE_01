// Component 1 - the dark palette shared by the gate screens
// (live_gate_check_screen.dart, guided_test_screen.dart).

import 'package:flutter/painting.dart';

abstract final class GateColors {
  static const Color bg = Color(0xFF0A0E14);
  static const Color surface = Color(0xFF131A24);
  static const Color surfaceRaised = Color(0xFF1A2330);
  static const Color stroke = Color(0xFF232E3D);
  static const Color accent = Color(0xFF22E6C9);
  static const Color accentDim = Color(0xFF0C9388);
  static const Color warn = Color(0xFFFFB24B);
  static const Color danger = Color(0xFFFF6B6B);
  static const Color textPrimary = Color(0xFFEFF4F8);
  static const Color textSecondary = Color(0xFF8C9AAE);
  static const Color textFaint = Color(0xFF5B6778);
}
