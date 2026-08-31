import "package:flutter/material.dart";
import "package:flutter/services.dart";
import "package:provider/provider.dart";

import "../models/models.dart" show ChatMode;
import "../state/app_state.dart";
import "../theme.dart";
import "../widgets/command_palette.dart";
import "../widgets/mode_selector.dart";
import "../widgets/privacy_indicator.dart";
import "admin_screen.dart";
import "chat_screen.dart";
import "document_screen.dart";
import "legal_updates_screen.dart";
import "skills_screen.dart";
import "settings_screen.dart";

/// Widescreen desktop shell: collapsible 260px sidebar + main area.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool sidebarOpen = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final state = context.read<AppState>();
      if (state.backendStatus == ConnectionStatus.unknown) state.checkHealth();
      // Load data based on auth status
      if (state.isAuthenticated) {
        state.loadSkills();
        state.loadLegalUpdates();
        state.loadToolConnections();
        if (state.isAdmin) state.loadAuditLogs();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Shortcuts(
      shortcuts: <ShortcutActivator, Intent>{
        const SingleActivator(LogicalKeyboardKey.keyK, control: true): const CommandPaletteIntent(),
        const SingleActivator(LogicalKeyboardKey.keyN, control: true): const NewChatIntent(),
        const SingleActivator(LogicalKeyboardKey.keyD, control: true, shift: true): const NewDocIntent(),
      },
      child: Actions(
        actions: <Type, Action<Intent>>{
          CommandPaletteIntent: CallbackAction<CommandPaletteIntent>(
              onInvoke: (_) => showCommandPalette(context)),
          NewChatIntent: CallbackAction<NewChatIntent>(onInvoke: (_) async => context.read<AppState>().newChat()),
          NewDocIntent: CallbackAction<NewDocIntent>(
              onInvoke: (_) async => context.read<AppState>().setView(MainView.document)),
        },
        child: Focus(
          autofocus: true,
          child: Scaffold(
            backgroundColor: AppColors.background,
            body: Row(
              children: [
                if (sidebarOpen) _Sidebar(width: 260, onToggle: () => setState(() {})),
                Expanded(
                  child: Column(
                    children: [
                      _TopBar(sidebarOpen: sidebarOpen, onToggleSidebar: () => setState(() => sidebarOpen = !sidebarOpen)),
                      if (state.mode == ChatMode.api)
                        _ApiBanner(),
                      Expanded(child: _mainArea(state)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _mainArea(AppState state) {
    switch (state.view) {
      case MainView.document:
        return const DocumentScreen();
      case MainView.settings:
        return const SettingsScreen();
      case MainView.admin:
        return state.isAdmin ? const AdminScreen() : _accessDenied();
      case MainView.legalUpdates:
        return const LegalUpdatesScreen();
      case MainView.skills:
        return const SkillsScreen();
      case MainView.research:
        return const ResearchScreen();
      default:
        return const ChatScreen();
    }
  }

  Widget _accessDenied() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.lock_outline, size: 48, color: AppColors.textSecondary),
          const SizedBox(height: 16),
          Text("Access Denied", style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Text("You don't have permission to view this page.", 
               style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------- sidebar

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.width, required this.onToggle});

  final double width;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return Container(
      width: width,
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(right: BorderSide(color: AppColors.border)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(width: 22, height: 22, decoration: BoxDecoration(color: AppColors.accent, borderRadius: BorderRadius.circular(6))),
          const SizedBox(width: 8),
          Text("Counsel AI", style: Theme.of(context).textTheme.titleMedium),
          const Spacer(),
          IconButton(onPressed: onToggle, icon: const Icon(Icons.menu_open, size: 18), tooltip: "Collapse"),
        ]),
        const SizedBox(height: 10),
        SizedBox(
          width: double.infinity,
          child: FilledButton.tonalIcon(
            onPressed: () => context.read<AppState>().newChat(),
            icon: const Icon(Icons.add, size: 18),
            label: const Text("New"),
            style: FilledButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: AppColors.textPrimary,
              side: const BorderSide(color: AppColors.border),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text("WORKSPACE", style: Theme.of(context).textTheme.labelSmall),
        const SizedBox(height: 4),
        _navItem(context, icon: Icons.chat_bubble_outline, label: "Ask", selected: state.view == MainView.chat, onTap: () => context.read<AppState>().setView(MainView.chat)),
        _navItem(context, icon: Icons.travel_explore, label: "Research", selected: state.view == MainView.chat && state.mode == ChatMode.research, onTap: () { final s = context.read<AppState>(); s.setMode(ChatMode.research); s.setView(MainView.chat); }),
        _navItem(context, icon: Icons.description_outlined, label: "Documents", selected: state.view == MainView.document, onTap: () => context.read<AppState>().setView(MainView.document)),
        const SizedBox(height: 16),
        Text("RECENT", style: Theme.of(context).textTheme.labelSmall),
        const SizedBox(height: 4),
        Expanded(
          child: ListView.builder(
            itemCount: state.conversations.length,
            itemBuilder: (context, i) {
              final c = state.conversations[i];
              return _recentTile(context, c.title, c.id == state.activeConversationId, () => context.read<AppState>().openConversation(c.id));
            },
          ),
        ),
        const Divider(color: AppColors.border),
        if (state.isAuthenticated) ...[
          _navItem(context, icon: Icons.auto_awesome_outlined, label: "Skills", selected: state.view == MainView.skills, onTap: () => context.read<AppState>().setView(MainView.skills)),
          _navItem(context, icon: Icons.newspaper_outlined, label: "Legal Updates", selected: state.view == MainView.legalUpdates, onTap: () => context.read<AppState>().setView(MainView.legalUpdates)),
        ],
        if (state.isAdmin)
          _navItem(context, icon: Icons.admin_panel_settings_outlined, label: "Admin", selected: state.view == MainView.admin, onTap: () => context.read<AppState>().setView(MainView.admin)),
        _navItem(context, icon: Icons.settings_outlined, label: "Settings", selected: state.view == MainView.settings, onTap: () => context.read<AppState>().setView(MainView.settings)),
        const SizedBox(height: 6),
        Row(children: [
          PrivacyDot(mode: state.mode, size: 8),
          const SizedBox(width: 8),
          Text(privacyLabel(state.mode), style: Theme.of(context).textTheme.bodySmall!.copyWith(color: AppColors.textSecondary)),
        ]),
      ]),
    );
  }

  Widget _navItem(BuildContext context,
      {required IconData icon, required String label, required bool selected, required VoidCallback onTap}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Material(
        color: selected ? Colors.white : Colors.transparent,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(8),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
            child: Row(children: [
              Icon(icon, size: 17, color: selected ? AppColors.accent : AppColors.textSecondary),
              const SizedBox(width: 10),
              Text(label, style: TextStyle(fontSize: 13.5, fontWeight: selected ? FontWeight.w600 : FontWeight.w400, color: AppColors.textPrimary)),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _recentTile(BuildContext context, String title, bool selected, VoidCallback onTap) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Material(
        color: selected ? Colors.white : Colors.transparent,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(onTap: onTap, borderRadius: BorderRadius.circular(8),
          child: Padding(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            child: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)))),
      ));
  }
}

// -------------------------------------------------------------------- topbar

class _TopBar extends StatelessWidget {
  const _TopBar({required this.sidebarOpen, required this.onToggleSidebar});

  final bool sidebarOpen;
  final VoidCallback onToggleSidebar;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return Container(
      height: 56,
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.border)),
        color: AppColors.background,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      child: Row(children: [
        if (!sidebarOpen)
          IconButton(onPressed: onToggleSidebar, icon: const Icon(Icons.menu, size: 20), tooltip: "Show sidebar"),
        if (!sidebarOpen) ...[
          Text("Counsel AI", style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(width: 16),
        ],
        ModeSelector(current: state.mode, onChanged: (m) => context.read<AppState>().setMode(m)),
        const Spacer(),
        ConnectionBadge(status: state.backendStatus),
        const SizedBox(width: 10),
        PrivacyChip(mode: state.mode),
      ]),
    );
  }
}

class _ApiBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        color: const Color(0xFFFEF3C7),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
        child: Row(children: [
          const Icon(Icons.cloud_upload_outlined, size: 15, color: Color(0xFFB45309)),
          const SizedBox(width: 8),
          Text("API mode: this conversation may be processed by an external provider. Avoid privileged client data.",
              style: Theme.of(context).textTheme.bodySmall!.copyWith(color: const Color(0xFFB45309))),
        ]),
      );
}
