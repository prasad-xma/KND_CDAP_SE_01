import 'package:flutter/material.dart';

class NavItem {
  final IconData icon;
  final String label;

  const NavItem({
    required this.icon,
    required this.label,
  });
}

class OrganicBottomNavBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;
  final List<NavItem> items;
  final Color themeColor;
  final Color itemColor;
  final Color activeTextColor;
  final Color inactiveIconColor;

  const OrganicBottomNavBar({
    super.key,
    required this.currentIndex,
    required this.onTap,
    required this.items,
    this.themeColor = const Color(0xFF0C9388),
    this.itemColor = Colors.white,
    this.activeTextColor = const Color(0xFF0C9388),
    this.inactiveIconColor = const Color(0xFF4A4A4A),
  });

  @override
  Widget build(BuildContext context) {
    const double itemHeight = 50.0;
    const double itemSpacing = 8.0;
    const double selectedWidth = 126.0;
    const double unselectedWidth = 48.0;
    const double padding = 6.0;

    // Align with widthFactor/heightFactor = 1.0 shrink-wraps to the child's
    // natural size (unlike Center, which expands to fill the parent's
    // constraints). This is what stops the nav bar from ballooning to fill
    // the whole bottomNavigationBar slot and covering the page content.
    return Align(
      alignment: Alignment.center,
      widthFactor: 1.0,
      heightFactor: 1.0,
      child: TweenAnimationBuilder<double>(
        tween: Tween<double>(begin: 0, end: currentIndex.toDouble()),
        duration: const Duration(milliseconds: 320),
        curve: Curves.easeInOutCubicEmphasized,
        builder: (context, animValue, child) {
          final List<Rect> animatedRects = [];
          double currentX = padding;

          for (int i = 0; i < items.length; i++) {
            final double activeFactor = (1.0 - (animValue - i).abs()).clamp(0.0, 1.0);
            final double width = unselectedWidth + (selectedWidth - unselectedWidth) * activeFactor;
            animatedRects.add(Rect.fromLTWH(currentX, padding, width, itemHeight));
            currentX += width + itemSpacing;
          }

          final double totalWidth = currentX - itemSpacing + padding;
          final double totalHeight = itemHeight + (padding * 2);

          return Container(
            decoration: BoxDecoration(
              boxShadow: [
                BoxShadow(
                  color: themeColor.withValues(alpha: 0.28),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: SizedBox(
              width: totalWidth,
              height: totalHeight,
              child: Stack(
                children: [
                  CustomPaint(
                    size: Size(totalWidth, totalHeight),
                    painter: RibbonPainter(
                      itemRects: animatedRects,
                      color: themeColor,
                    ),
                  ),
                  Positioned.fill(
                    child: Padding(
                      padding: const EdgeInsets.all(padding),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: List.generate(items.length, (index) {
                          final bool isSelected = index == currentIndex;
                          final NavItem item = items[index];

                          return GestureDetector(
                            onTap: () => onTap(index),
                            behavior: HitTestBehavior.opaque,
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 300),
                              curve: Curves.easeInOutCubicEmphasized,
                              width: isSelected ? selectedWidth : unselectedWidth,
                              height: itemHeight,
                              decoration: BoxDecoration(
                                color: itemColor,
                                borderRadius: BorderRadius.circular(itemHeight / 2),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    item.icon,
                                    color: isSelected ? activeTextColor : inactiveIconColor,
                                    size: 22,
                                  ),
                                  if (isSelected) ...[
                                    const SizedBox(width: 6),
                                    Flexible(
                                      child: Text(
                                        item.label,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: TextStyle(
                                          color: activeTextColor,
                                          fontWeight: FontWeight.w700,
                                          fontSize: 13,
                                          letterSpacing: 0.2,
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          );
                        }),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class RibbonPainter extends CustomPainter {
  final List<Rect> itemRects;
  final Color color;

  RibbonPainter({required this.itemRects, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (itemRects.isEmpty) return;

    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.fill
      ..isAntiAlias = true;

    const double dip = 7.0;
    const double borderPadding = 5.0;

    final List<RRect> rrects = itemRects.map((r) {
      final expanded = r.inflate(borderPadding);
      return RRect.fromRectAndRadius(
        expanded,
        Radius.circular(expanded.height / 2),
      );
    }).toList();

    final path = Path();

    path.moveTo(rrects.first.left + rrects.first.height / 2, rrects.first.top);

    for (int i = 0; i < rrects.length; i++) {
      final curr = rrects[i];
      final rCapX = curr.right - curr.height / 2;

      path.lineTo(rCapX, curr.top);

      if (i < rrects.length - 1) {
        final next = rrects[i + 1];
        final nextLCapX = next.left + next.height / 2;
        final midX = (rCapX + nextLCapX) / 2;
        final midY = ((curr.top + next.top) / 2) + dip;

        path.quadraticBezierTo(midX, midY, nextLCapX, next.top);
      } else {
        path.arcToPoint(
          Offset(curr.right - curr.height / 2, curr.bottom),
          radius: Radius.circular(curr.height / 2),
          clockwise: true,
        );
      }
    }

    for (int i = rrects.length - 1; i >= 0; i--) {
      final curr = rrects[i];
      final lCapX = curr.left + curr.height / 2;

      path.lineTo(lCapX, curr.bottom);

      if (i > 0) {
        final prev = rrects[i - 1];
        final prevRCapX = prev.right - prev.height / 2;
        final midX = (lCapX + prevRCapX) / 2;
        final midY = ((curr.bottom + prev.bottom) / 2) - dip;

        path.quadraticBezierTo(midX, midY, prevRCapX, prev.bottom);
      } else {
        path.arcToPoint(
          Offset(curr.left + curr.height / 2, curr.top),
          radius: Radius.circular(curr.height / 2),
          clockwise: true,
        );
      }
    }

    path.close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant RibbonPainter oldDelegate) => true;
}