import "package:flutter/material.dart";
import "package:provider/provider.dart";
import "package:url_launcher/url_launcher.dart";

import "../models/models.dart";
import "../state/app_state.dart";
import "../theme.dart";

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController baseUrlCtrl;
  late final TextEditingController tokenCtrl;
  late final TextEditingController apiKeyCtrl;
  bool obscureKey = true;
  bool savingServer = false;

  @override
  void initState() {
    super.initState();
    final state = context.read<AppState>();
    baseUrlCtrl = TextEditingController(text: state.baseUrl);
    tokenCtrl = TextEditingController(text: state.apiToken);
    apiKeyCtrl = TextEditingController(text: state.apiKey);
  }

  @override
  void dispose() {
    baseUrlCtrl.dispose();
    tokenCtrl.dispose();
    apiKeyCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final connected = state.backendStatus == ConnectionStatus.connected;

    return ListView(
      padding: const EdgeInsets.fromLTRB(28, 28, 28, 48),
      children: [
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 820),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text("Settings",
                    style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 6),
                Text(
                  "Connection, privacy, and integrations. Only settings backed by the app are shown here.",
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium
                      ?.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(height: 28),
                _Section(
                  title: "Backend",
                  icon: Icons.dns_outlined,
                  child: Column(
                    children: [
                      TextField(
                        controller: baseUrlCtrl,
                        keyboardType: TextInputType.url,
                        decoration: const InputDecoration(
                          labelText: "Server URL",
                          hintText: "http://127.0.0.1:8000",
                          prefixIcon: Icon(Icons.link, size: 18),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: tokenCtrl,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: "Server token",
                          prefixIcon: Icon(Icons.key_outlined, size: 18),
                        ),
                      ),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          FilledButton.icon(
                            onPressed: savingServer
                                ? null
                                : () async {
                                    final url = baseUrlCtrl.text.trim();
                                    if (url.isEmpty) {
                                      _snack("Enter a server URL first.");
                                      return;
                                    }
                                    setState(() => savingServer = true);
                                    try {
                                      await state.saveServerConfig(
                                          url, tokenCtrl.text.trim());
                                      if (mounted)
                                        _snack(
                                            "Saved. Backend status refreshed.");
                                    } catch (e) {
                                      if (mounted)
                                        _snack("Could not connect: $e");
                                    } finally {
                                      if (mounted)
                                        setState(() => savingServer = false);
                                    }
                                  },
                            icon: savingServer
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2))
                                : const Icon(Icons.refresh, size: 17),
                            label: Text(savingServer
                                ? "Reconnecting…"
                                : "Save & reconnect"),
                          ),
                          const SizedBox(width: 12),
                          _StatusPill(
                              connected: connected,
                              label: connected ? "Connected" : "Offline"),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                _Section(
                  title: "Provider API key",
                  icon: Icons.cloud_outlined,
                  subtitle:
                      "Used only for API mode. The key is stored with OS secure storage.",
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: apiKeyCtrl,
                          obscureText: obscureKey,
                          decoration: const InputDecoration(
                            labelText: "OpenAI-compatible API key",
                            prefixIcon: Icon(Icons.vpn_key_outlined, size: 18),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        tooltip: obscureKey ? "Show key" : "Hide key",
                        onPressed: () =>
                            setState(() => obscureKey = !obscureKey),
                        icon: Icon(obscureKey
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined),
                      ),
                      FilledButton.tonal(
                        onPressed: () async {
                          await state.saveApiKey(apiKeyCtrl.text.trim());
                          if (mounted) _snack("API key saved securely.");
                        },
                        child: const Text("Save"),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                _Section(
                  title: "Integrations",
                  icon: Icons.extension_outlined,
                  subtitle: state.isAuthenticated
                      ? "Connect accounts through the configured backend."
                      : "Sign in to enable account integrations.",
                  child: Column(
                    children: [
                      _IntegrationRow(
                          label: "Gmail",
                          provider: "gmail",
                          icon: Icons.mail_outline,
                          state: state,
                          enabled: state.isAuthenticated),
                      const Divider(height: 1),
                      _IntegrationRow(
                          label: "Outlook",
                          provider: "outlook",
                          icon: Icons.mark_email_unread_outlined,
                          state: state,
                          enabled: state.isAuthenticated),
                      const Divider(height: 1),
                      _IntegrationRow(
                          label: "Google Calendar",
                          provider: "google_calendar",
                          icon: Icons.calendar_month_outlined,
                          state: state,
                          enabled: state.isAuthenticated),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                _Section(
                  title: "Local model",
                  icon: Icons.memory_outlined,
                  subtitle:
                      "Availability is reported by the backend rather than simulated in the UI.",
                  child: connected
                      ? FutureBuilder<Map<String, dynamic>>(
                          future: state.api.health(),
                          builder: (context, snapshot) {
                            if (!snapshot.hasData)
                              return const _InfoRow(
                                  icon: Icons.sync,
                                  text: "Checking local model…");
                            final services = snapshot.data?["services"];
                            final local =
                                services is Map ? services["local_llm"] : null;
                            final available =
                                local is Map && local["available"] == true;
                            return _InfoRow(
                              icon: available
                                  ? Icons.check_circle_outline
                                  : Icons.info_outline,
                              color: available
                                  ? AppColors.success
                                  : AppColors.warning,
                              text: available
                                  ? "Local model is available."
                                  : "No local model is available. Configure LOCAL_MODEL_PATH in the backend.",
                            );
                          },
                        )
                      : const _InfoRow(
                          icon: Icons.cloud_off_outlined,
                          text:
                              "Connect to the backend to check local model status."),
                ),
                const SizedBox(height: 16),
                _Section(
                  title: "About",
                  icon: Icons.info_outline,
                  child: Column(
                    children: [
                      _ActionRow(
                        icon: Icons.description_outlined,
                        title: "Repository",
                        subtitle: "Open-source project and documentation",
                        onTap: () => _openExternal(
                            "https://github.com/App-netizen-arch/special-octo-chainsaw"),
                      ),
                      const Divider(height: 1),
                      _ActionRow(
                        icon: Icons.bug_report_outlined,
                        title: "Report an issue",
                        subtitle: "Open the repository issue tracker",
                        onTap: () => _openExternal(
                            "https://github.com/App-netizen-arch/special-octo-chainsaw/issues"),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  void _snack(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _openExternal(String url) async {
    final ok =
        await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    if (!ok && mounted) _snack("Could not open the link.");
  }
}

class _Section extends StatelessWidget {
  const _Section(
      {required this.title,
      required this.icon,
      this.subtitle,
      required this.child});
  final String title;
  final IconData icon;
  final String? subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(9)),
              child: Icon(icon, size: 18, color: AppColors.textSecondary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleMedium),
                    if (subtitle != null) ...[
                      const SizedBox(height: 3),
                      Text(subtitle!,
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(color: AppColors.textSecondary)),
                    ],
                  ]),
            ),
          ]),
          const SizedBox(height: 18),
          child,
        ]),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.connected, required this.label});
  final bool connected;
  final String label;

  @override
  Widget build(BuildContext context) {
    final color = connected ? AppColors.success : AppColors.warning;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(999)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.circle, size: 8, color: color),
        const SizedBox(width: 7),
        Text(label,
            style: TextStyle(
                color: color, fontSize: 12, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.text, this.color});
  final IconData icon;
  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) =>
      Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, size: 18, color: color ?? AppColors.textSecondary),
        const SizedBox(width: 10),
        Expanded(
            child: Text(text, style: Theme.of(context).textTheme.bodyMedium)),
      ]);
}

class _ActionRow extends StatelessWidget {
  const _ActionRow(
      {required this.icon,
      required this.title,
      required this.subtitle,
      required this.onTap});
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(icon, size: 19, color: AppColors.textSecondary),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.open_in_new, size: 17),
        onTap: onTap,
      );
}

class _IntegrationRow extends StatelessWidget {
  const _IntegrationRow(
      {required this.label,
      required this.provider,
      required this.icon,
      required this.state,
      required this.enabled});
  final String label;
  final String provider;
  final IconData icon;
  final AppState state;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    ToolConnection? connection;
    for (final item in state.toolConnections) {
      if (item.provider == provider) {
        connection = item;
        break;
      }
    }
    final isConnected = connection?.isConnected == true;

    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon,
          size: 20,
          color: isConnected ? AppColors.success : AppColors.textSecondary),
      title: Text(label),
      subtitle: Text(
        isConnected
            ? (connection?.userEmail?.isNotEmpty == true
                ? connection!.userEmail!
                : "Connected")
            : enabled
                ? "Not connected"
                : "Sign in to connect",
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: isConnected
          ? OutlinedButton(
              onPressed: () => _disconnect(context),
              child: const Text("Disconnect"))
          : FilledButton.tonal(
              onPressed: enabled ? () => _connect(context) : null,
              child: const Text("Connect")),
    );
  }

  Future<void> _disconnect(BuildContext context) async {
    try {
      await state.disconnectTool(provider);
      if (context.mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text("$label disconnected.")));
    } catch (e) {
      if (context.mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text("Could not disconnect: $e")));
    }
  }

  Future<void> _connect(BuildContext context) async {
    try {
      final authUrl = await state.initiateToolConnection(provider);
      final opened = await launchUrl(Uri.parse(authUrl),
          mode: LaunchMode.externalApplication);
      if (!opened)
        throw Exception("The authorization page could not be opened.");
      if (!context.mounted) return;

      final code = await showDialog<String>(
          context: context, builder: (_) => _CodeDialog(provider: label));
      if (code == null || code.trim().isEmpty || !context.mounted) return;
      await state.completeToolConnection(provider, code.trim());
      if (context.mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text("$label connected.")));
    } catch (e) {
      if (context.mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text("Connection failed: $e")));
    }
  }
}

class _CodeDialog extends StatefulWidget {
  const _CodeDialog({required this.provider});
  final String provider;

  @override
  State<_CodeDialog> createState() => _CodeDialogState();
}

class _CodeDialogState extends State<_CodeDialog> {
  final controller = TextEditingController();

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text("Finish ${widget.provider} connection"),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
              labelText: "Authorization code",
              hintText: "Paste the code returned by the provider"),
          onSubmitted: (value) => Navigator.pop(context, value),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text("Cancel")),
          FilledButton(
              onPressed: () => Navigator.pop(context, controller.text),
              child: const Text("Complete")),
        ],
      );
}
