import "package:flutter/material.dart";
import "package:provider/provider.dart";

import "../models/models.dart";
import "../state/app_state.dart";
import "chat_screen.dart";

/// Research uses the same streaming conversation pipeline as Ask.
/// Keeping one pipeline prevents the old screen from owning a second,
/// incomplete source/progress state machine.
class ResearchScreen extends StatefulWidget {
  const ResearchScreen({super.key});

  @override
  State<ResearchScreen> createState() => _ResearchScreenState();
}

class _ResearchScreenState extends State<ResearchScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final state = context.read<AppState>();
      state.setMode(ChatMode.research);
      state.setView(MainView.chat);
    });
  }

  @override
  Widget build(BuildContext context) => const ChatScreen();
}
