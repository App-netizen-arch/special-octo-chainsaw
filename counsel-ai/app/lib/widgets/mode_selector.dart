import "package:flutter/material.dart";

import "../models/models.dart";
import "../theme.dart";

class ModeSelector extends StatelessWidget {
  const ModeSelector({super.key, required this.current, required this.onChanged});

  final ChatMode current;
  final ValueChanged<ChatMode> onChanged;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = MediaQuery.sizeOf(context).width < 620;
        if (compact) {
          return PopupMenuButton<ChatMode>(
            tooltip: "Choose mode",
            onSelected: onChanged,
            itemBuilder: (context) => [
              for (final mode in ChatMode.values)
                PopupMenuItem(value: mode, child: Text(mode.label)),
            ],
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.border),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.tune, size: 16, color: AppColors.textSecondary),
                const SizedBox(width: 6),
                Text(current.label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                const SizedBox(width: 2),
                const Icon(Icons.keyboard_arrow_down, size: 16, color: AppColors.textSecondary),
              ]),
            ),
          );
        }

        return Container(
          padding: const EdgeInsets.all(3),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.border),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [for (final mode in ChatMode.values) _segment(mode, selected: mode == current)],
          ),
        );
      },
    );
  }

  Widget _segment(ChatMode mode, {required bool selected}) {
    return InkWell(
      onTap: () => onChanged(mode),
      borderRadius: BorderRadius.circular(8),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? Colors.white : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: selected ? Border.all(color: AppColors.border) : null,
        ),
        child: Text(
          mode.label,
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
