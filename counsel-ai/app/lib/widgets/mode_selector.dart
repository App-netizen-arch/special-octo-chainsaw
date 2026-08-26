import "package:flutter/material.dart";

import "../models/models.dart";
import "../theme.dart";

/// Segmented control in the top bar: Local / API / Research / Tools.
class ModeSelector extends StatelessWidget {
  const ModeSelector({super.key, required this.current, required this.onChanged});

  final ChatMode current;
  final ValueChanged<ChatMode> onChanged;

  static const modes = ChatMode.values;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final m in modes)
            _segment(m, selected: m == current),
        ],
      ),
    );
  }

  Widget _segment(ChatMode m, {required bool selected}) {
    return GestureDetector(
      onTap: () => onChanged(m),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? Colors.white : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: selected ? Border.all(color: AppColors.border) : null,
          boxShadow: selected
              ? [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 3, offset: const Offset(0, 1))]
              : null,
        ),
        child: Text(
          m.label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
            color: selected ? AppColors.textPrimary : AppColors.textSecondary,
          ),
        ),
      ),
    );
  }
}
