## component 01

Acoustic Robustness & Noise Handling: the quality gate that every recording
passes through before it reaches Component 2 (phonation) or Component 3 (DDK).

### Files
- `quality_gate.dart`: `QualityGate.check(...)`, the single entry point other screens call
- `services/quality_gate_api_service.dart`: HTTP client for `POST /quality/check` (port 8001)
- `models/quality_report.dart`: `QualityReport` (the report.json fields the app uses; the full report stays on the server), `QualityTask`, `QualityGateRejected`

### Run
```
cd parkinson-speech-ai
uvicorn component1_robustness.api:app --reload --host 0.0.0.0 --port 8001   # gate
uvicorn component2_phonation.api:app --reload --host 0.0.0.0 --port 8000    # phonation
cd ../neurovox && flutter run -d chrome
```

### Usage
```dart
try {
  await QualityGate.check(task: QualityTask.vowel, filePath: path); // or bytes: on web
  // PASS -> send to Component 2/3
} on QualityGateRejected catch (e) {
  // FAIL -> show e.report.userMessage and ask for a new recording
}
```

`guided_test_screen.dart` (opened by Home's **Start Test**): a 2-step test.
Step 1 of 2 is one "aaaa" take (gate task `vowel`, then Component 2). Step 2 of 2
is one "pa-ta-ka" take (gate task `ddk`; the motor result is "coming soon" until
Component 3 has an API). A rejected take shows the gate's message, and the user
re-records that step.

Also wired into `features/phonation/phonation_test_screen.dart`. Each of
the 3 vowel takes is gated as soon as it is recorded. A rejected take is
discarded and the user re-records that same take. Component 3 can do the same
with `QualityTask.ddk`.

Set `QualityGate.enabled = false` to bypass the gate while developing without the server.
