import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:neurovox/main.dart';
import 'package:neurovox/screens/auth/login_screen.dart';

void main() {
  testWidgets('NeuroVox splash screen loads smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const NeuroVoxApp());

    // Verify that the title and tagline are present.
    expect(find.text('NeuroVox'), findsOneWidget);
    expect(find.text("AI-Powered Parkinson's Voice Biomarkers"), findsOneWidget);
    expect(find.text('Get Started'), findsOneWidget);
  });

  testWidgets('login opens the home screen with bottom navigation', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: LoginScreen()));

    await tester.enterText(find.byType(TextFormField).at(0), 'Alex');
    await tester.enterText(find.byType(TextFormField).at(1), 'password');
    await tester.ensureVisible(find.widgetWithText(ElevatedButton, 'Log In'));
    await tester.tap(find.widgetWithText(ElevatedButton, 'Log In'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.textContaining('Hello, Alex'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.record_voice_over_outlined));
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Phonation'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.settings_voice_outlined));
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Motor'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.analytics_outlined));
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Reports'), findsOneWidget);
  });
}
