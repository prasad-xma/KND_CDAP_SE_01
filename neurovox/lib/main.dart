import 'package:flutter/material.dart';
import 'screens/splash_screen.dart';

void main() {
  runApp(const NeuroVoxApp());
}

class NeuroVoxApp extends StatelessWidget {
  const NeuroVoxApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NeuroVox',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF0C9388),
          primary: const Color(0xFF0C9388),
          surface: const Color(0xFFD6ECE6),
        ),
        useMaterial3: true,
      ),
      home: const SplashScreen(),
    );
  }
}
