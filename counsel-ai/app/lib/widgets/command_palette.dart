import "package:flutter/material.dart";
import "package:provider/provider.dart";

import "../models/models.dart" show ChatMode;
import "../state/app_state.dart";
import "../theme.dart";

/// Ctrl+K command palette: quick navigation + common actions.
Future<void> showCommandPalette(BuildContext context) {
  return showDialog(
    context: context,
    builder: (context) => const _CommandPalette(),
  );
}

class CommandPaletteIntent extends Intent {
  const CommandPaletteIntent();
}

class NewChatIntent extends Intent {
  const NewChatIntent();
}

class NewDocIntent extends Intent {
  const NewDocIntent();
}

class _Command {
  const _Command(this.label, this.hint, this.run);
  final String label;
  final String hint;
  final void Function(BuildContext) run;
}

class _CommandPalette extends StatefulWidget {
  const _CommandPalette();

  @override
  State<_CommandPalette> createState() => _CommandPaletteState();
}

class _CommandPaletteState extends State<_CommandPalette> {
  String query = "";
  late final List<_Command> commands;

  @override
  void initState() {
    super.initState();
    commands = [
      _Command("New chat", "Ctrl+N", (c) => c.read<AppState>().newChat()),
      _Command("Open documents", "Documents", (c) => c.read<AppState>().setView(MainView.document)),
      _Command("Research mode", "Mode", (c) => c.read<AppState>().setMode(ChatMode.research)),
      _Command("Local mode", "Mode", (c) => c.read<AppState>().setMode(ChatMode.local)),
      _Command("API mode", "Mode", (c) => c.read<AppState>().setMode(ChatMode.api)),
      _Command("Tools mode", "Mode", (c) => c.read<AppState>().setMode(ChatMode.tools)),
      _Command("Settings", "", (c) => c.read<AppState>().setView(MainView.settings)),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final filtered = query.isEmpty
        ? commands
        : commands.where((c) => c.label.toLowerCase().contains(query.toLowerCase())).toList();
    return Dialog(
      backgroundColor: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: const BorderSide(color: AppColors.border)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480, maxHeight: 380),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
              autofocus: true,
              decoration: const InputDecoration(hintText: "Type a command…", prefixIcon: Icon(Icons.search, size: 18)),
              onChanged: (v) => setState(() => query = v),
            ),
            const SizedBox(height: 8),
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: filtered.length,
                itemBuilder: (context, i) {
                  final cmd = filtered[i];
                  return ListTile(
                    dense: true,
                    title: Text(cmd.label, style: const TextStyle(fontSize: 13.5)),
                    trailing: Text(cmd.hint, style: Theme.of(context).textTheme.labelSmall),
                    onTap: () {
                      Navigator.of(context).pop();
                      cmd.run(context);
                    },
                  );
                },
              ),
            ),
          ]),
        ),
      ),
    );
  }
}
