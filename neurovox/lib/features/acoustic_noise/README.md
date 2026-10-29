## component 01

Acoustic Robustness & Noise Handling: the quality gate that every recording
passes through before it reaches Component 2 (phonation) or Component 3 (DDK).

### Files
- `quality_gate.dart`: `QualityGate.check(...)`, the single entry point other screens call
- `services/quality_gate_api_service.dart`: HTTP client (port 8001): `check(...)` for `POST /quality/check` (bytes on web, file path elsewhere), `fetchThresholds()`, `plotUrl(...)`; `GateServerException` when the server can't be reached
- `gate_colors.dart`: `GateColors`, the dark palette both screens use
- `models/quality_report.dart`: `QualityReport` (report.json: decision, score, message, plus the measured quality, voice check and biomarker changes), `GateThresholds` (from `GET /health`), `QualityTask`, `QualityGateRejected`
- `take_recorder.dart`: `TakeRecorder`, one 5 s take with the 5 -> 0 countdown (stops at 4.8 s), shared by both screens below
- `live_gate_check_screen.dart`: Home's **Live Mic Test** tile. Record one take and see the gate's decision, each check against its threshold, what enhancement did, and the waveform/spectrogram plots (`GET /quality/plots/<clip_id>/<name>`). Gate only, no Component 2/3.

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

`guided_test_screen.dart` (currently not opened anywhere; Home's **Start Test** button does nothing): a 2-step test.
Step 1 of 2 is one "aaaa" take (gate task `vowel`, then Component 2). Step 2 of 2
is one "pa-ta-ka" take (gate task `ddk`; the motor result is "coming soon" until
Component 3 has an API). A rejected take shows the gate's message, and the user
re-records that step.

Also wired into `features/phonation/phonation_test_screen.dart`. Each of
the 3 vowel takes is gated as soon as it is recorded. A rejected take is
discarded and the user re-records that same take. Component 3 can do the same
with `QualityTask.ddk`.

Set `QualityGate.enabled = false` to bypass the gate while developing without the server.
