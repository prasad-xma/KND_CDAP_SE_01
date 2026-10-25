// Dev-only entry point for Component 2 (phonation) work in isolation.
// Run with: flutter run -t lib/main_phonation_dev.dart -d chrome
//
// This is separate from the real app's lib/main.dart on purpose, so testing
// your own screen never touches main.dart or anyone else's files directly.
// The real app reaches this same screen via home_screen.dart's
// "Phonation Test" bottom-nav tab.

import 'package:flutter/material.dart';

import 'features/phonation/phonation_test_screen.dart';

void main() {
  runApp(const PhonationDevApp());
}

class PhonationDevApp extends StatelessWidget {
  const PhonationDevApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Phonation Dev',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0C9388)),
        useMaterial3: true,
      ),
      home: const PhonationTestScreen(),
    );
  }
}
