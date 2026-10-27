import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/i18n/language_controller.dart';
import '../core/widgets/bottom_nav_bar.dart';
import '../core/widgets/language_toggle_button.dart';
import '../features/phonation/phonation_test_screen.dart';
import 'speech_motor_test_screen.dart';
import 'reports_screen.dart';

const Color _bg = Color(0xFF0A0E14);
const Color _surfaceRaised = Color(0xFF1A2330);
const Color _stroke = Color(0xFF232E3D);
const Color _accent = Color(0xFF22E6C9);
const Color _accentDim = Color(0xFF0C9388);
const Color _textPrimary = Color(0xFFEFF4F8);
const Color _textSecondary = Color(0xFF8C9AAE);
const Color _textFaint = Color(0xFF5B6778);

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

  void _goToPhonationTab() => setState(() => _currentIndex = 1);

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = [
      _buildHomeDashboardTab(),
      const PhonationTestScreen(),
      const SpeechMotorTestScreen(),
      const ReportsScreen(),
    ];

    return ListenableBuilder(
      listenable: LanguageController.instance,
      builder: (context, _) {
        return AnnotatedRegion<SystemUiOverlayStyle>(
          value: const SystemUiOverlayStyle(
            statusBarColor: Colors.transparent,
            statusBarIconBrightness: Brightness.light,
            statusBarBrightness: Brightness.dark,
          ),
          child: Scaffold(
            backgroundColor: _bg,
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
                  themeColor: _accent,
                  itemColor: _surfaceRaised,
                  activeTextColor: _accent,
                  inactiveIconColor: _textSecondary,
                  items: [
                    NavItem(icon: Icons.home_outlined, label: tr('navHome')),
                    NavItem(icon: Icons.record_voice_over_outlined, label: tr('navPhonation')),
                    NavItem(icon: Icons.settings_voice_outlined, label: tr('navMotor')),
                    NavItem(icon: Icons.analytics_outlined, label: tr('navReports')),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildHomeDashboardTab() {
    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 12.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Row(
                  children: [
                    Container(
                      width: 46,
                      height: 46,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [_accent, _accentDim],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: _accent.withValues(alpha: 0.25),
                            blurRadius: 10,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: const Center(
                        child: Icon(Icons.person_rounded, color: Color(0xFF071210), size: 26),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${tr('hello')}, ${widget.userName} 👋',
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w800,
                              color: _textPrimary,
                              letterSpacing: -0.3,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 2),
                          Text(
                            tr('vocalDashboard'),
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: _textSecondary,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              const LanguageToggleButton(
                activeColor: _accent,
                inactiveColor: _textSecondary,
                backgroundColor: _surfaceRaised,
              ),
            ],
          ),

          const SizedBox(height: 20),

          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [_accent, _accentDim],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: _accent.withValues(alpha: 0.25),
                  blurRadius: 22,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.graphic_eq_rounded, color: Color(0xFF071210), size: 20),
                    SizedBox(width: 8),
                    Text(
                      'Phonation Screening',
                      style: TextStyle(
                        color: Color(0xFF071210),
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                const Text(
                  'Run a sustained-vowel voice test to check your acoustic biomarkers.',
                  style: TextStyle(
                    color: Color(0xCC071210),
                    fontSize: 13,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 18),
                ElevatedButton.icon(
                  onPressed: _goToPhonationTab,
                  icon: const Icon(Icons.mic_none_rounded, color: _accentDim, size: 20),
                  label: const Text(
                    'Start Test',
                    style: TextStyle(
                      color: _accentDim,
                      fontWeight: FontWeight.w800,
                      fontSize: 14,
                    ),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF071210),
                    foregroundColor: _accentDim,
                    elevation: 0,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 26),

          const Text(
            'Assessment Modules',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: _textPrimary,
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
                iconColor: _accent,
                onTap: () => setState(() => _currentIndex = 1),
              ),
              _buildActionCard(
                icon: Icons.record_voice_over_rounded,
                title: 'Speech-Motor',
                subtitle: 'Passage reading task',
                iconColor: const Color(0xFF5B9BFF),
                onTap: () => setState(() => _currentIndex = 2),
              ),
              _buildActionCard(
                icon: Icons.analytics_outlined,
                title: 'Risk Reports',
                subtitle: 'Fusion diagnostics',
                iconColor: const Color(0xFFBB86FC),
                onTap: () => setState(() => _currentIndex = 3),
              ),
              _buildActionCard(
                icon: Icons.mic_external_on_outlined,
                title: 'Live Mic Test',
                subtitle: 'Real-time assessment',
                iconColor: const Color(0xFFFFB24B),
                onTap: _goToPhonationTab,
              ),
            ],
          ),
          const SizedBox(height: 26),

          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Recent Assessments',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: _textPrimary,
                  letterSpacing: -0.3,
                ),
              ),
              TextButton(
                onPressed: () => setState(() => _currentIndex = 3),
                child: const Text(
                  'See All',
                  style: TextStyle(
                    color: _accent,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              color: _surfaceRaised,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: _stroke),
            ),
            child: Column(
              children: [
                const Icon(Icons.history_rounded, color: _textFaint, size: 26),
                const SizedBox(height: 10),
                const Text(
                  'No assessments yet',
                  style: TextStyle(fontWeight: FontWeight.w700, color: _textPrimary, fontSize: 13.5),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Run a phonation test to see results here.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12.5, color: _textSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _buildActionCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required Color iconColor,
    required VoidCallback onTap,
  }) {
    return Material(
      color: _surfaceRaised,
      borderRadius: BorderRadius.circular(20),
      elevation: 0,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _stroke),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: iconColor.withValues(alpha: 0.15),
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
                  color: _textPrimary,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 11,
                  color: _textSecondary,
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
}
