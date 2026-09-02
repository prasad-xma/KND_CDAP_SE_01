import 'package:flutter_test/flutter_test.dart';
import 'package:neurovox/main.dart';

void main() {
  testWidgets('NeuroVox splash screen loads smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const NeuroVoxApp());

    // Verify that the title and tagline are present.
    expect(find.text('NeuroVox'), findsOneWidget);
    expect(find.text("AI-Powered Parkinson's Voice Biomarkers"), findsOneWidget);
    expect(find.text('Get Started'), findsOneWidget);
  });
}
