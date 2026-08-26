import "package:flutter/material.dart";

import "../models/models.dart";
import "../state/app_state.dart" show ConnectionStatus;
import "../theme.dart";

/// Small backend connectivity badge shown in the top bar.
class ConnectionBadge extends StatelessWidget {
  const ConnectionBadge({super.key, required this.status});

  final ConnectionStatus status;

  @override
  Widget build(BuildContext context) {
    final (color, label) = switch (status) {
      ConnectionStatus.connected => (AppColors.success, "Backend"),
      ConnectionStatus.offline => (AppColors.danger, "Offline"),
      ConnectionStatus.unknown => (AppColors.textSecondary, "Checking"),
    };
    return Tooltip(
      message: status == ConnectionStatus.connected
          ? "Connected to the Counsel AI backend"
          : "Cannot reach the backend. Start it with: uvicorn app.main:app",
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 5),
        Text(label, style: TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
      ]),
    );
  }
}

Color privacyColor(ChatMode mode) => switch (mode) {
      ChatMode.local => AppColors.privacyLocal,
      ChatMode.api => AppColors.privacyApi,
      ChatMode.tools => AppColors.privacyTool,
      ChatMode.research => AppColors.accent,
    };

String privacyLabel(ChatMode mode) => switch (mode) {
      ChatMode.local => "Private · Local mode",
      ChatMode.api => "API mode",
      ChatMode.research => "Research mode",
      ChatMode.tools => "Tools mode",
    };

class PrivacyDot extends StatelessWidget {
  const PrivacyDot({super.key, required this.mode, this.size = 9});

  final ChatMode mode;
  final double size;

  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(color: privacyColor(mode), shape: BoxShape.circle),
      );
}

class PrivacyChip extends StatelessWidget {
  const PrivacyChip({super.key, required this.mode});

  final ChatMode mode;

  @override
  Widget build(BuildContext context) {
    final color = privacyColor(mode);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        PrivacyDot(mode: mode),
        const SizedBox(width: 6),
        Text(privacyLabel(mode), style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: color)),
      ]),
    );
  }
}
