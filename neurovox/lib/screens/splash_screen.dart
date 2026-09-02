import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'get_started_screen.dart';

/// Clean, modern UI mockup of a splash screen for the medical mobile app "NeuroVox".
/// 
/// Palette:
/// - Background: Soft mint green (#D6ECE6)
/// - Primary / Accent: Vibrant teal (#0C9388)
/// - Secondary / Tagline: Dark grey (#666666)
class SplashScreen extends StatefulWidget {
  final VoidCallback? onGetStarted;

  const SplashScreen({
    super.key,
    this.onGetStarted,
  });

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _fadeAnimation;
  late final Animation<double> _scaleAnimation;
  late final Animation<double> _waveAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    );

    _fadeAnimation = CurvedAnimation(
      parent: _controller,
      curve: const Interval(0.0, 0.65, curve: Curves.easeOut),
    );

    _scaleAnimation = Tween<double>(begin: 0.88, end: 1.0).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.0, 0.65, curve: Curves.easeOutBack),
      ),
    );

    _waveAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.3, 1.0, curve: Curves.easeInOut),
      ),
    );

    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const Color bgMint = Color(0xFFD6ECE6);
    const Color primaryTeal = Color(0xFF0C9388);
    const Color primaryTealLight = Color(0xFF0EC4B7);
    const Color darkGrey = Color(0xFF666666);

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
      ),
      child: Scaffold(
        backgroundColor: bgMint,
        body: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              return Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 32.0,
                  vertical: 24.0,
                ),
                child: Column(
                  children: [
                    const Spacer(flex: 2),

                    // Center Upper Area: Logo, Title, and Tagline
                    FadeTransition(
                      opacity: _fadeAnimation,
                      child: ScaleTransition(
                        scale: _scaleAnimation,
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            // Stylized Brain + Soundwaves Logo Card
                            Container(
                              width: 140,
                              height: 140,
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(40),
                                boxShadow: [
                                  BoxShadow(
                                    color: primaryTeal.withValues(alpha: 0.18),
                                    blurRadius: 36,
                                    offset: const Offset(0, 12),
                                  ),
                                  BoxShadow(
                                    color: Colors.black.withValues(alpha: 0.04),
                                    blurRadius: 10,
                                    offset: const Offset(0, 2),
                                  ),
                                ],
                              ),
                              child: Center(
                                child: AnimatedBuilder(
                                  animation: _waveAnimation,
                                  builder: (context, child) {
                                    return CustomPaint(
                                      size: const Size(92, 92),
                                      painter: NeuroVoxLogoPainter(
                                        color: primaryTeal,
                                        progress: _waveAnimation.value,
                                      ),
                                    );
                                  },
                                ),
                              ),
                            ),
                            const SizedBox(height: 32),

                            // App Title "NeuroVox"
                            const Text(
                              'NeuroVox',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 40,
                                fontWeight: FontWeight.w800,
                                letterSpacing: -1.2,
                                color: primaryTeal,
                                fontFamily: 'SF Pro Display',
                              ),
                            ),
                            const SizedBox(height: 12),

                            // Subtle Tagline
                            const Padding(
                              padding: EdgeInsets.symmetric(horizontal: 16.0),
                              child: Text(
                                "AI-Powered Parkinson's Voice Biomarkers",
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w500,
                                  letterSpacing: 0.2,
                                  color: darkGrey,
                                  height: 1.45,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),

                    const Spacer(flex: 3),

                    // Bottom Area: Loading Indicator & Get Started Button
                    FadeTransition(
                      opacity: _fadeAnimation,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // Minimal Loading Indicator (Pulsing soundwave dots)
                          AnimatedBuilder(
                            animation: _controller,
                            builder: (context, child) {
                              return Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: List.generate(3, (index) {
                                  final double phase = (_controller.value * 2 * math.pi) + (index * 0.8);
                                  final double dotScale = 0.6 + (0.4 * (0.5 + 0.5 * math.sin(phase)));
                                  final double opacity = 0.3 + (0.7 * (0.5 + 0.5 * math.sin(phase)));

                                  return Transform.scale(
                                    scale: dotScale,
                                    child: Container(
                                      margin: const EdgeInsets.symmetric(horizontal: 4),
                                      width: 7,
                                      height: 7,
                                      decoration: BoxDecoration(
                                        color: primaryTeal.withValues(alpha: opacity),
                                        shape: BoxShape.circle,
                                      ),
                                    ),
                                  );
                                }),
                              );
                            },
                          ),
                          const SizedBox(height: 24),

                          // Clean Rounded Teal "Get Started" Button
                          Container(
                            width: double.infinity,
                            height: 56,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(20),
                              gradient: const LinearGradient(
                                colors: [primaryTealLight, primaryTeal],
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: primaryTeal.withValues(alpha: 0.38),
                                  blurRadius: 24,
                                  offset: const Offset(0, 10),
                                ),
                                BoxShadow(
                                  color: primaryTeal.withValues(alpha: 0.15),
                                  blurRadius: 6,
                                  offset: const Offset(0, 2),
                                ),
                              ],
                            ),
                            child: Material(
                              color: Colors.transparent,
                              child: InkWell(
                                borderRadius: BorderRadius.circular(20),
                                onTap: () {
                                  HapticFeedback.lightImpact();
                                  if (widget.onGetStarted != null) {
                                    widget.onGetStarted!();
                                  } else {
                                    Navigator.of(context).push(
                                      MaterialPageRoute(
                                        builder: (_) => const GetStartedScreen(),
                                      ),
                                    );
                                  }
                                },
                                child: const Center(
                                  child: Text(
                                    'Get Started',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 17,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: 0.3,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 14),

                          // Subtle iOS Home Indicator spacing / footer caption
                          Text(
                            'Clinical Grade Vocal Analysis',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                              color: darkGrey.withValues(alpha: 0.6),
                              letterSpacing: 0.4,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

/// Custom painter for rendering the stylized human brain outline
/// combined seamlessly with audio soundwaves in vibrant teal.
class NeuroVoxLogoPainter extends CustomPainter {
  final Color color;
  final double progress;

  NeuroVoxLogoPainter({
    required this.color,
    required this.progress,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final double w = size.width;
    final double h = size.height;

    final Paint outlinePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.8
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final Paint innerFoldsPaint = Paint()
      ..color = color.withValues(alpha: 0.55)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round;

    final Paint wavePaint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;

    // --- 1. Left Hemisphere Outline ---
    final Path leftBrainPath = Path();
    leftBrainPath.moveTo(w * 0.50, h * 0.16);
    leftBrainPath.cubicTo(
      w * 0.38, h * 0.16,
      w * 0.28, h * 0.20,
      w * 0.22, h * 0.28,
    );
    leftBrainPath.cubicTo(
      w * 0.15, h * 0.25,
      w * 0.08, h * 0.30,
      w * 0.09, h * 0.40,
    );
    leftBrainPath.cubicTo(
      w * 0.05, h * 0.46,
      w * 0.07, h * 0.56,
      w * 0.12, h * 0.62,
    );
    leftBrainPath.cubicTo(
      w * 0.14, h * 0.70,
      w * 0.24, h * 0.75,
      w * 0.35, h * 0.74,
    );
    leftBrainPath.lineTo(w * 0.50, h * 0.74);
    canvas.drawPath(leftBrainPath, outlinePaint);

    // --- 2. Right Hemisphere Outline ---
    final Path rightBrainPath = Path();
    rightBrainPath.moveTo(w * 0.50, h * 0.16);
    rightBrainPath.cubicTo(
      w * 0.62, h * 0.16,
      w * 0.72, h * 0.20,
      w * 0.78, h * 0.28,
    );
    rightBrainPath.cubicTo(
      w * 0.85, h * 0.25,
      w * 0.92, h * 0.30,
      w * 0.91, h * 0.40,
    );
    rightBrainPath.cubicTo(
      w * 0.95, h * 0.46,
      w * 0.93, h * 0.56,
      w * 0.88, h * 0.62,
    );
    rightBrainPath.cubicTo(
      w * 0.86, h * 0.70,
      w * 0.76, h * 0.75,
      w * 0.65, h * 0.74,
    );
    rightBrainPath.lineTo(w * 0.50, h * 0.74);
    canvas.drawPath(rightBrainPath, outlinePaint);

    // --- 3. Inner Folds / Gyri & Sulci ---
    // Left side gyri
    final Path leftFold1 = Path()
      ..moveTo(w * 0.22, h * 0.36)
      ..quadraticBezierTo(w * 0.32, h * 0.30, w * 0.40, h * 0.36);
    canvas.drawPath(leftFold1, innerFoldsPaint);

    final Path leftFold2 = Path()
      ..moveTo(w * 0.16, h * 0.48)
      ..quadraticBezierTo(w * 0.26, h * 0.42, w * 0.36, h * 0.49);
    canvas.drawPath(leftFold2, innerFoldsPaint);

    final Path leftFold3 = Path()
      ..moveTo(w * 0.20, h * 0.61)
      ..quadraticBezierTo(w * 0.29, h * 0.55, w * 0.39, h * 0.62);
    canvas.drawPath(leftFold3, innerFoldsPaint);

    // Right side gyri
    final Path rightFold1 = Path()
      ..moveTo(w * 0.78, h * 0.36)
      ..quadraticBezierTo(w * 0.68, h * 0.30, w * 0.60, h * 0.36);
    canvas.drawPath(rightFold1, innerFoldsPaint);

    final Path rightFold2 = Path()
      ..moveTo(w * 0.84, h * 0.48)
      ..quadraticBezierTo(w * 0.74, h * 0.42, w * 0.64, h * 0.49);
    canvas.drawPath(rightFold2, innerFoldsPaint);

    final Path rightFold3 = Path()
      ..moveTo(w * 0.80, h * 0.61)
      ..quadraticBezierTo(w * 0.71, h * 0.55, w * 0.61, h * 0.62);
    canvas.drawPath(rightFold3, innerFoldsPaint);

    // --- 4. Central Fissure Line ---
    final Paint fissurePaint = Paint()
      ..color = color.withValues(alpha: 0.4)
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(
      Offset(w * 0.50, h * 0.20),
      Offset(w * 0.50, h * 0.72),
      fissurePaint,
    );

    // --- 5. Integrated Audio Soundwaves (Equalizer Bars) ---
    // 5 soundwave bars emerging at the base
    const int barCount = 5;
    final List<double> barHeights = [10.0, 16.0, 24.0, 16.0, 10.0];
    const double barWidth = 4.2;
    const double barSpacing = 4.8;
    final double totalWaveWidth = (barCount * barWidth) + ((barCount - 1) * barSpacing);
    final double waveStartX = (w - totalWaveWidth) / 2;
    final double waveBaseY = h * 0.86;

    for (int i = 0; i < barCount; i++) {
      final double targetHeight = barHeights[i];
      // Subtle rhythmic movement with animation progress
      final double waveFactor = 0.8 + 0.2 * math.sin(progress * 2 * math.pi + (i * 0.8));
      final double currentHeight = targetHeight * waveFactor;
      final double x = waveStartX + (i * (barWidth + barSpacing));
      final double y = waveBaseY - (currentHeight / 2);

      final RRect barRect = RRect.fromRectAndRadius(
        Rect.fromLTWH(x, y, barWidth, currentHeight),
        const Radius.circular(2.5),
      );

      final double alpha = i == 2 ? 1.0 : (i == 1 || i == 3 ? 0.78 : 0.55);
      wavePaint.color = color.withValues(alpha: alpha);
      canvas.drawRRect(barRect, wavePaint);
    }
  }

  @override
  bool shouldRepaint(covariant NeuroVoxLogoPainter oldDelegate) {
    return oldDelegate.progress != progress || oldDelegate.color != color;
  }
}
