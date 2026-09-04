import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/widgets/bottom_nav_bar.dart';

class HomeScreen extends StatefulWidget {
  final String userName;

  const HomeScreen({
    super.key,
    this.userName = 'Alex',
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with SingleTickerProviderStateMixin {
  int _currentIndex = 0;
  bool _isRecordingSimulated = false;
  late final AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  void _showRecordVoiceModal() {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color primaryTealLight = Color(0xFF0EC4B7);
    const Color darkGrey = Color(0xFF2D3748);
    const Color lightGrey = Color(0xFF718096);

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (modalContext) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Container(
              height: MediaQuery.of(context).size.height * 0.72,
              decoration: const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.vertical(top: Radius.circular(32)),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
              child: Column(
                children: [
                  Container(
                    width: 44,
                    height: 5,
                    decoration: BoxDecoration(
                      color: Colors.grey.shade300,
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Vocal Biomarker Check',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          color: darkGrey,
                        ),
                      ),
                      IconButton(
                        onPressed: () => Navigator.pop(modalContext),
                        icon: const Icon(Icons.close_rounded, color: lightGrey),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Please pronounce a steady sustained vowel /a/ into the microphone for 5 seconds.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 14,
                      color: lightGrey,
                      height: 1.4,
                    ),
                  ),
                  const Spacer(),
                  SizedBox(
                    height: 100,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: List.generate(24, (index) {
                        final double barHeight = _isRecordingSimulated
                            ? 15.0 + 65.0 * math.sin((index * 0.3) + (_pulseController.value * math.pi * 2)).abs()
                            : 8.0 + (index % 4) * 4.0;

                        return Container(
                          margin: const EdgeInsets.symmetric(horizontal: 2.5),
                          width: 4,
                          height: barHeight,
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [primaryTealLight, primaryTeal],
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                            ),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        );
                      }),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    _isRecordingSimulated ? 'Listening & Analyzing Frequency...' : 'Ready to record',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: _isRecordingSimulated ? primaryTeal : lightGrey,
                    ),
                  ),
                  const Spacer(),
                  GestureDetector(
                    onTap: () {
                      setModalState(() {
                        _isRecordingSimulated = !_isRecordingSimulated;
                      });
                      setState(() {});

                      if (_isRecordingSimulated) {
                        Future.delayed(const Duration(seconds: 4), () {
                          if (modalContext.mounted) {
                            Navigator.pop(modalContext);
                            _showSuccessAssessmentDialog();
                          }
                          setState(() {
                            _isRecordingSimulated = false;
                          });
                        });
                      }
                    },
                    child: Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: LinearGradient(
                          colors: _isRecordingSimulated
                              ? [Colors.redAccent, Colors.red]
                              : [primaryTealLight, primaryTeal],
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: (_isRecordingSimulated ? Colors.red : primaryTeal)
                                .withValues(alpha: 0.4),
                            blurRadius: 24,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      child: Icon(
                        _isRecordingSimulated ? Icons.stop_rounded : Icons.mic_rounded,
                        color: Colors.white,
                        size: 38,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    _isRecordingSimulated ? 'Tap to cancel' : 'Tap mic to start test',
                    style: const TextStyle(fontSize: 13, color: lightGrey),
                  ),
                  const SizedBox(height: 12),
                ],
              ),
            );
          },
        );
      },
    );
  }

  void _showSuccessAssessmentDialog() {
    const Color primaryTeal = Color(0xFF0C9388);

    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
          backgroundColor: Colors.white,
          title: const Row(
            children: [
              Icon(Icons.check_circle_rounded, color: primaryTeal, size: 28),
              SizedBox(width: 10),
              Text(
                'Analysis Complete',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Your vocal biomarkers have been processed successfully.',
                style: TextStyle(color: Color(0xFF4A4A4A), fontSize: 14),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFFD6ECE6).withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Voice Stability Score:',
                      style: TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF2D3748)),
                    ),
                    Text(
                      '96% (Optimal)',
                      style: TextStyle(fontWeight: FontWeight.w800, color: primaryTeal),
                    ),
                  ],
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text(
                'View Detailed Report',
                style: TextStyle(color: primaryTeal, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        );
      },
    );
  }

  void _showNotificationsSheet() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      backgroundColor: Colors.white,
      builder: (ctx) {
        return Container(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.notifications_active_outlined, color: Color(0xFF0C9388)),
                  SizedBox(width: 10),
                  Text(
                    'Notifications',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFD6ECE6),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.alarm_rounded, color: Color(0xFF0C9388)),
                ),
                title: const Text('Daily Assessment Reminder', style: TextStyle(fontWeight: FontWeight.bold)),
                subtitle: const Text('Take your 30-second morning vowel stability check.'),
              ),
              const Divider(),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFE2E8F0),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.analytics_outlined, color: Color(0xFF4A4A4A)),
                ),
                title: const Text('Weekly Health Digest', style: TextStyle(fontWeight: FontWeight.bold)),
                subtitle: const Text('Your voice stability improved by +3.2% this week.'),
              ),
              const SizedBox(height: 12),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    const Color bgMint = Color(0xFFD6ECE6);
    const Color primaryTeal = Color(0xFF0C9388);

    final List<Widget> pages = [
      _buildHomeDashboardTab(),
      _buildPhonationTestTab(),
      _buildSpeechMotorTab(),
      _buildReportsTab(),
    ];

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
      ),
      child: Scaffold(
        backgroundColor: bgMint,
        body: SafeArea(
          child: IndexedStack(
            index: _currentIndex,
            children: pages,
          ),
        ),
        bottomNavigationBar: SafeArea(
          child: Padding(
            padding: const EdgeInsets.only(bottom: 12.0, top: 4.0),
            child: BottomNavBar(
              currentIndex: _currentIndex,
              onTap: (index) => setState(() => _currentIndex = index),
              themeColor: primaryTeal,
              items: const [
                NavItem(icon: Icons.home_outlined, label: 'Home'),
                NavItem(icon: Icons.record_voice_over_outlined, label: 'Phonation'),
                NavItem(icon: Icons.settings_voice_outlined, label: 'Motor'),
                NavItem(icon: Icons.analytics_outlined, label: 'Reports'),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ================= TAB 0: HOME DASHBOARD =================
  Widget _buildHomeDashboardTab() {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color primaryTealLight = Color(0xFF0EC4B7);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 12.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Top Header Bar
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [primaryTealLight, primaryTeal],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: primaryTeal.withValues(alpha: 0.25),
                          blurRadius: 10,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: const Center(
                      child: Icon(Icons.person_rounded, color: Colors.white, size: 26),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Hello, ${widget.userName} 👋',
                        style: const TextStyle(
                          fontSize: 19,
                          fontWeight: FontWeight.w800,
                          color: darkSlate,
                          letterSpacing: -0.3,
                        ),
                      ),
                      const SizedBox(height: 2),
                      const Text(
                        'Vocal Health Dashboard',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: mediumGrey,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              IconButton(
                onPressed: _showNotificationsSheet,
                icon: Stack(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(9),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: primaryTeal.withValues(alpha: 0.1),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.notifications_none_rounded,
                        color: primaryTeal,
                        size: 22,
                      ),
                    ),
                    Positioned(
                      right: 3,
                      top: 3,
                      child: Container(
                        width: 9,
                        height: 9,
                        decoration: const BoxDecoration(
                          color: Colors.redAccent,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Hero Health Score Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF0F9B90), Color(0xFF08756C)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: primaryTeal.withValues(alpha: 0.35),
                  blurRadius: 22,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.shield_outlined, color: Colors.white, size: 14),
                          SizedBox(width: 5),
                          Text(
                            'Baseline Normal',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.local_fire_department_rounded, color: Colors.amberAccent, size: 15),
                          SizedBox(width: 4),
                          Text(
                            '7-Day Streak',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Voice Stability',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        SizedBox(height: 4),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.baseline,
                          textBaseline: TextBaseline.alphabetic,
                          children: [
                            Text(
                              '94',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 42,
                                fontWeight: FontWeight.w900,
                                height: 1.0,
                              ),
                            ),
                            Text(
                              '%',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 22,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    ElevatedButton.icon(
                      onPressed: _showRecordVoiceModal,
                      icon: const Icon(Icons.mic_none_rounded, color: primaryTeal, size: 20),
                      label: const Text(
                        'Quick Test',
                        style: TextStyle(
                          color: primaryTeal,
                          fontWeight: FontWeight.w800,
                          fontSize: 14,
                        ),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: primaryTeal,
                        elevation: 0,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(
                    value: 0.94,
                    minHeight: 6,
                    backgroundColor: Colors.white.withValues(alpha: 0.25),
                    valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 26),

          // Assessment Modules Section
          const Text(
            'Assessment Modules',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 14),

          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 2,
            crossAxisSpacing: 14,
            mainAxisSpacing: 14,
            childAspectRatio: 1.25,
            children: [
              _buildActionCard(
                icon: Icons.graphic_eq_rounded,
                title: 'Phonation Test',
                subtitle: 'Pitch & Jitter check',
                badgeColor: const Color(0xFFE6F8F5),
                iconColor: primaryTeal,
                onTap: () => setState(() => _currentIndex = 1),
              ),
              _buildActionCard(
                icon: Icons.record_voice_over_rounded,
                title: 'Speech-Motor',
                subtitle: 'Passage reading task',
                badgeColor: const Color(0xFFEFF6FF),
                iconColor: const Color(0xFF2563EB),
                onTap: () => setState(() => _currentIndex = 2),
              ),
              _buildActionCard(
                icon: Icons.analytics_outlined,
                title: 'Risk Reports',
                subtitle: 'Fusion diagnostics',
                badgeColor: const Color(0xFFFAF5FF),
                iconColor: const Color(0xFF9333EA),
                onTap: () => setState(() => _currentIndex = 3),
              ),
              _buildActionCard(
                icon: Icons.mic_external_on_outlined,
                title: 'Live Mic Test',
                subtitle: 'Real-time assessment',
                badgeColor: const Color(0xFFFFF7ED),
                iconColor: const Color(0xFFEA580C),
                onTap: _showRecordVoiceModal,
              ),
            ],
          ),
          const SizedBox(height: 26),

          // Recent Assessments Timeline
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Recent Assessments',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: darkSlate,
                  letterSpacing: -0.3,
                ),
              ),
              TextButton(
                onPressed: () => setState(() => _currentIndex = 3),
                child: const Text(
                  'See All',
                  style: TextStyle(
                    color: primaryTeal,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          _buildRecentTestItem(
            title: 'Sustained Vowel /a/ Test',
            time: 'Today • 10:30 AM',
            stability: '96% Score',
            isOptimal: true,
          ),
          const SizedBox(height: 10),
          _buildRecentTestItem(
            title: 'Cognitive Sentence Reading',
            time: 'Yesterday • 04:15 PM',
            stability: '93% Score',
            isOptimal: true,
          ),
          const SizedBox(height: 10),
          _buildRecentTestItem(
            title: 'Phonation Frequency Sweep',
            time: 'Aug 30 • 09:00 AM',
            stability: '88% Score',
            isOptimal: false,
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  // ================= TAB 1: PHONATION TEST =================
  Widget _buildPhonationTestTab() {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Phonation Test',
            style: TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Sustained vowel acoustic biomarker assessment',
            style: TextStyle(fontSize: 14, color: mediumGrey, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 24),

          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: primaryTeal.withValues(alpha: 0.08),
                  blurRadius: 18,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: Column(
              children: [
                Container(
                  width: 90,
                  height: 90,
                  decoration: const BoxDecoration(
                    color: Color(0xFFD6ECE6),
                    shape: BoxShape.circle,
                  ),
                  child: const Center(
                    child: Icon(Icons.record_voice_over_rounded, size: 48, color: primaryTeal),
                  ),
                ),
                const SizedBox(height: 18),
                const Text(
                  'Sustained /a/ Vowel Task',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: darkSlate),
                ),
                const SizedBox(height: 10),
                const Text(
                  'Take a deep breath and vocalize a steady "/a/" sound into the microphone for 5 continuous seconds at a comfortable pitch.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 14, color: mediumGrey, height: 1.5),
                ),
                const SizedBox(height: 24),
                ElevatedButton.icon(
                  onPressed: _showRecordVoiceModal,
                  icon: const Icon(Icons.play_arrow_rounded, color: Colors.white),
                  label: const Text(
                    'Begin Phonation Task',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: primaryTeal,
                    minimumSize: const Size(double.infinity, 54),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Diagnostic Metrics Preview
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: primaryTeal.withValues(alpha: 0.06),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Extracted Acoustic Parameters', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 14),
                _buildMetricRow('Fundamental Freq (F0)', '124.5 Hz', 'Optimal'),
                const Divider(),
                _buildMetricRow('Jitter (local)', '0.34%', 'Normal (< 1.0%)'),
                const Divider(),
                _buildMetricRow('Shimmer (apq3)', '1.82%', 'Normal (< 3.0%)'),
                const Divider(),
                _buildMetricRow('Harmonics-to-Noise (HNR)', '22.4 dB', 'Good (> 20 dB)'),
              ],
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  // ================= TAB 2: SPEECH-MOTOR TEST =================
  Widget _buildSpeechMotorTab() {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Speech-Motor Test',
            style: TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Articulatory coordination & DDK syllable repetition',
            style: TextStyle(fontSize: 14, color: mediumGrey, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 24),

          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: primaryTeal.withValues(alpha: 0.08),
                  blurRadius: 18,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFEFF6FF),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: const Icon(Icons.settings_voice_rounded, color: Color(0xFF2563EB), size: 28),
                    ),
                    const SizedBox(width: 14),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Diadochokinetic (DDK) Rate',
                            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
                          ),
                          Text(
                            'Repeat "PA-TA-KA" rapidly',
                            style: TextStyle(color: mediumGrey, fontSize: 13),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                const Text(
                  'Instructions:\nRepeat the syllables "pa-ta-ka" as fast and evenly as possible for 10 seconds. Keep an even cadence.',
                  style: TextStyle(color: darkSlate, fontSize: 14, height: 1.5),
                ),
                const SizedBox(height: 20),
                ElevatedButton(
                  onPressed: _showRecordVoiceModal,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF2563EB),
                    minimumSize: const Size(double.infinity, 50),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                  child: const Text('Start DDK Speech Task', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  // ================= TAB 3: REPORTS & RISK ANALYSIS =================
  Widget _buildReportsTab() {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Reports & Risk Analysis',
            style: TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: darkSlate,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Multi-modal vocal biomarker fusion results',
            style: TextStyle(fontSize: 14, color: mediumGrey, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 24),

          Container(
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: primaryTeal.withValues(alpha: 0.08),
                  blurRadius: 18,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Neurological Vocal Risk', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: const Color(0xFFE6F8F5),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Text(
                        'Low Risk (Optimal)',
                        style: TextStyle(color: primaryTeal, fontWeight: FontWeight.w800, fontSize: 12),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text('94.2%', style: TextStyle(fontSize: 38, fontWeight: FontWeight.w900, color: primaryTeal)),
                  ],
                ),
                const Text('Confidence Index: 98.6%', style: TextStyle(color: mediumGrey, fontSize: 13)),
                const SizedBox(height: 20),
                ElevatedButton.icon(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: const Text('Exporting Clinician PDF Report...'),
                        backgroundColor: primaryTeal,
                        behavior: SnackBarBehavior.floating,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    );
                  },
                  icon: const Icon(Icons.picture_as_pdf_outlined, color: Colors.white),
                  label: const Text('Export Clinician PDF', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: primaryTeal,
                    minimumSize: const Size(double.infinity, 50),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _buildMetricRow(String label, String value, String status) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF2D3748), fontSize: 13)),
          Row(
            children: [
              Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF0C9388), fontSize: 13)),
              const SizedBox(width: 8),
              Text('($status)', style: const TextStyle(fontSize: 11, color: Color(0xFF64748B))),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildActionCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required Color badgeColor,
    required Color iconColor,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(20),
      elevation: 0,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF0C9388).withValues(alpha: 0.06),
                blurRadius: 14,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: badgeColor,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: iconColor, size: 22),
              ),
              const Spacer(),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF1E293B),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 11,
                  color: Color(0xFF64748B),
                  fontWeight: FontWeight.w500,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildRecentTestItem({
    required String title,
    required String time,
    required String stability,
    required bool isOptimal,
  }) {
    const Color primaryTeal = Color(0xFF0C9388);
    const Color darkSlate = Color(0xFF1E293B);
    const Color mediumGrey = Color(0xFF64748B);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: primaryTeal.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFFD6ECE6),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.graphic_eq_rounded, color: primaryTeal, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                    color: darkSlate,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  time,
                  style: const TextStyle(
                    fontSize: 12,
                    color: mediumGrey,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: isOptimal
                  ? const Color(0xFFE6F8F5)
                  : const Color(0xFFFEF3C7),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              stability,
              style: TextStyle(
                color: isOptimal ? primaryTeal : const Color(0xFFD97706),
                fontWeight: FontWeight.w800,
                fontSize: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
