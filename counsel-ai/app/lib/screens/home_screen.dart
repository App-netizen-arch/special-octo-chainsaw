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
import "research_screen.dart";
import "settings_screen.dart";
import "skills_screen.dart";

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
          CommandPaletteIntent: CallbackAction<CommandPaletteIntent>(onInvoke: (_) => showCommandPalette(context)),
          NewChatIntent: CallbackAction<NewChatIntent>(onInvoke: (_) => context.read<AppState>().newChat()),
          NewDocIntent: CallbackAction<NewDocIntent>(onInvoke: (_) => context.read<AppState>().setView(MainView.document)),
        },
        child: Focus(
          autofocus: true,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 820;
              if (compact) {
                return Scaffold(
                  backgroundColor: AppColors.background,
                  drawer: Drawer(
                    backgroundColor: AppColors.surface,
                    child: SafeArea(child: _Sidebar(onNavigate: () => Navigator.of(context).pop())),
                  ),
                  body: Column(
                    children: [
                      _TopBar(compact: true, sidebarOpen: false, onToggleSidebar: () => Scaffold.of(context).openDrawer()),
                      if (state.mode == ChatMode.api) const _ApiBanner(),
                      Expanded(child: _mainArea(state)),
                    ],
                  ),
                );
              }

              return Scaffold(
                backgroundColor: AppColors.background,
                body: Row(
                  children: [
                    if (sidebarOpen) _Sidebar(onNavigate: () {}),
                    Expanded(
                      child: Column(
                        children: [
                          _TopBar(
                            compact: false,
                            sidebarOpen: sidebarOpen,
                            onToggleSidebar: () => setState(() => sidebarOpen = !sidebarOpen),
                          ),
                          if (state.mode == ChatMode.api) const _ApiBanner(),
                          Expanded(child: _mainArea(state)),
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
      case MainView.chat:
        return const ChatScreen();
    }
  }

  Widget _accessDenied() => Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.lock_outline, size: 44, color: AppColors.textSecondary),
            const SizedBox(height: 12),
            Text("Access Denied", style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 6),
            Text(
              "You don't have permission to view this page.",
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary),
            ),
          ],
        ),
      );
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.onNavigate});

  final VoidCallback onNavigate;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 14, 12, 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(color: AppColors.accent, borderRadius: BorderRadius.circular(7)),
                child: const Icon(Icons.balance, size: 14, color: Colors.white),
              ),
              const SizedBox(width: 9),
              Text("Counsel AI", style: Theme.of(context).textTheme.titleMedium),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton.tonalIcon(
              onPressed: () {
                state.newChat();
                onNavigate();
              },
              icon: const Icon(Icons.add, size: 18),
              label: const Text("New chat"),
              style: FilledButton.styleFrom(
                backgroundColor: Colors.white,
                foregroundColor: AppColors.textPrimary,
                side: const BorderSide(color: AppColors.border),
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ),
          const SizedBox(height: 18),
          Text("WORKSPACE", style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 5),
          _nav(context, Icons.chat_bubble_outline, "Ask", state.view == MainView.chat && state.mode != ChatMode.research, () {
            state.setMode(ChatMode.local);
            state.setView(MainView.chat);
            onNavigate();
          }),
          _nav(context, Icons.travel_explore, "Research", state.view == MainView.chat && state.mode == ChatMode.research, () {
            state.setMode(ChatMode.research);
            state.setView(MainView.chat);
            onNavigate();
          }),
          _nav(context, Icons.description_outlined, "Documents", state.view == MainView.document, () {
            state.setView(MainView.document);
            onNavigate();
          }),
          const SizedBox(height: 14),
          Text("RECENT", style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 5),
          Expanded(
            child: state.conversations.isEmpty
                ? Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
                    child: Text(
                      "Your recent conversations will appear here.",
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textSecondary),
                    ),
                  )
                : ListView.builder(
                    itemCount: state.conversations.length,
                    itemBuilder: (context, i) {
                      final conversation = state.conversations[i];
                      return _recent(
                        context,
                        conversation.title,
                        conversation.id == state.activeConversationId,
                        () async {
                          await state.openConversation(conversation.id);
                          onNavigate();
                        },
                      );
                    },
                  ),
          ),
          const Divider(color: AppColors.border),
          if (state.isAuthenticated) ...[
            _nav(context, Icons.auto_awesome_outlined, "Skills", state.view == MainView.skills, () {
              state.setView(MainView.skills);
              onNavigate();
            }),
            _nav(context, Icons.newspaper_outlined, "Legal updates", state.view == MainView.legalUpdates, () {
              state.setView(MainView.legalUpdates);
              onNavigate();
            }),
          ],
          if (state.isAdmin)
            _nav(context, Icons.admin_panel_settings_outlined, "Admin", state.view == MainView.admin, () {
              state.setView(MainView.admin);
              onNavigate();
            }),
          _nav(context, Icons.settings_outlined, "Settings", state.view == MainView.settings, () {
            state.setView(MainView.settings);
            onNavigate();
          }),
          const SizedBox(height: 8),
          Row(
            children: [
              PrivacyDot(mode: state.mode, size: 8),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  privacyLabel(state.mode),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textSecondary),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _nav(BuildContext context, IconData icon, String label, bool selected, VoidCallback onTap) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Material(
        color: selected ? Colors.white : Colors.transparent,
        borderRadius: BorderRadius.circular(9),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(9),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
            child: Row(
              children: [
                Icon(icon, size: 17, color: selected ? AppColors.accent : AppColors.textSecondary),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    label,
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _recent(BuildContext context, String title, bool selected, VoidCallback onTap) {
    return Material(
      color: selected ? Colors.white : Colors.transparent,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
        ),
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({required this.compact, required this.sidebarOpen, required this.onToggleSidebar});

  final bool compact;
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
      padding: const EdgeInsets.symmetric(horizontal: 10),
      child: Row(
        children: [
          IconButton(
            onPressed: onToggleSidebar,
            icon: Icon(compact || !sidebarOpen ? Icons.menu : Icons.menu_open, size: 20),
            tooltip: compact || !sidebarOpen ? "Open navigation" : "Collapse navigation",
          ),
          if (compact || !sidebarOpen) ...[
            Text("Counsel AI", style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(width: 10),
          ],
          if (compact)
            PopupMenuButton<ChatMode>(
              tooltip: "Change mode",
              onSelected: state.setMode,
              itemBuilder: (context) => [
                for (final mode in ChatMode.values)
                  PopupMenuItem(value: mode, child: Text(mode.label)),
              ],
              child: Chip(label: Text(state.mode.label)),
            )
          else
            Flexible(child: ModeSelector(current: state.mode, onChanged: state.setMode)),
          const Spacer(),
          if (!compact) ConnectionBadge(status: state.backendStatus),
          if (!compact) const SizedBox(width: 8),
          PrivacyChip(mode: state.mode),
        ],
      ),
    );
  }
}

class _ApiBanner extends StatelessWidget {
  const _ApiBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: const Color(0xFFFEF3C7),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
      child: Row(
        children: [
          const Icon(Icons.cloud_upload_outlined, size: 15, color: Color(0xFFB45309)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              "API mode: responses may be processed by an external provider. Avoid privileged client data.",
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFFB45309)),
            ),
          ),
        ],
      ),
    );
  }
}
