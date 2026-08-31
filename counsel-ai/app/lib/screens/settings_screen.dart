import "package:flutter/material.dart";
import "package:flutter/services.dart";
import "package:provider/provider.dart";
import "package:url_launcher/url_launcher.dart";

import "../state/app_state.dart";
import "../theme.dart";

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController baseUrlCtrl;
  late TextEditingController tokenCtrl;
  late TextEditingController apiKeyCtrl;
  bool obscureKey = true;
  
  // Model settings
  String selectedModelId = "";
  int contextLength = 4096;
  double temperature = 0.7;
  
  // Privacy settings
  bool dataRetentionEnabled = true;
  bool showEncryptionStatus = true;
  
  // Appearance settings
  ThemeMode appTheme = ThemeMode.system;
  double fontSize = 14.0;
  
  // Auto-update
  bool autoUpdateEnabled = true;

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
    final health = state.backendStatus == ConnectionStatus.connected;
    
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: ListView(
          padding: const EdgeInsets.all(36),
          children: [
            Text("Settings", style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 24),

            // ---------------------------------------------------- backend
            _sectionTitle(context, "Backend connection"),
            TextField(controller: baseUrlCtrl, decoration: const InputDecoration(labelText: "Server URL")),
            const SizedBox(height: 12),
            TextField(controller: tokenCtrl, decoration: const InputDecoration(labelText: "Local auth token")),
            const SizedBox(height: 12),
            Row(children: [
              FilledButton(
                onPressed: () async {
                  await state.saveServerConfig(baseUrlCtrl.text.trim(), tokenCtrl.text.trim());
                  if (mounted) setState(() {});
                },
                child: const Text("Save & reconnect"),
              ),
              const SizedBox(width: 12),
              Icon(health ? Icons.check_circle : Icons.error_outline,
                  size: 17, color: health ? AppColors.success : AppColors.danger),
              const SizedBox(width: 6),
              Text(health ? "Connected" : "Backend unreachable",
                  style: TextStyle(fontSize: 13, color: health ? AppColors.success : AppColors.danger)),
            ]),
            const SizedBox(height: 32),

            // --------------------------------------------------- api key
            _sectionTitle(context, "Provider API key (API mode)"),
            Text("Stored in this machine's OS keychain. Sent to your backend per request; never written to disk.",
                style: Theme.of(context).textTheme.bodySmall!.copyWith(color: AppColors.textSecondary)),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(
                child: TextField(
                  controller: apiKeyCtrl,
                  obscureText: obscureKey,
                  decoration: const InputDecoration(labelText: "DeepSeek / OpenAI-compatible key"),
                ),
              ),
              IconButton(onPressed: () => setState(() => obscureKey = !obscureKey), icon: const Icon(Icons.visibility_outlined, size: 18)),
              FilledButton.tonal(onPressed: () => state.saveApiKey(apiKeyCtrl.text.trim()), child: const Text("Save key")),
            ]),
            const SizedBox(height: 32),

            // ------------------------------------------------- local model
            _sectionTitle(context, "Local model"),
            Text("Local mode runs a GGUF file on this machine via llama.cpp. Set LOCAL_MODEL_PATH in the backend .env and restart it; the status below refreshes automatically.",
                style: Theme.of(context).textTheme.bodySmall!.copyWith(color: AppColors.textSecondary)),
            const SizedBox(height: 8),
            FutureBuilder<dynamic>(
              future: health ? state.api.health() : null,
              builder: (context, snap) {
                if (!health) return const Text("Backend offline.", style: TextStyle(color: AppColors.textSecondary));
                if (!snap.hasData) return const Text("Checking…", style: TextStyle(color: AppColors.textSecondary));
                final local = snap.data!["services"]["local_llm"] as Map<String, dynamic>? ?? {};
                final ok = local["available"] == true;
                return Row(children: [
                  Icon(ok ? Icons.check_circle : Icons.info_outline, size: 16, color: ok ? AppColors.success : AppColors.warning),
                  const SizedBox(width: 6),
                  Text(ok ? "Local model ready" : "No GGUF model found — set LOCAL_MODEL_PATH",
                      style: TextStyle(fontSize: 13)),
                ]);
              },
            ),
            const SizedBox(height: 32),

            // ------------------------------------------------- Model Settings
            _sectionTitle(context, "Model Settings"),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    DropdownButtonFormField<String>(
                      value: selectedModelId.isEmpty ? null : selectedModelId,
                      decoration: const InputDecoration(labelText: "Model", border: OutlineInputBorder()),
                      items: const [
                        DropdownMenuItem(value: "deepseek-coder-1.3b-base", child: Text("DeepSeek Coder 1.3B")),
                        DropdownMenuItem(value: "mistral-7b-instruct", child: Text("Mistral 7B Instruct")),
                        DropdownMenuItem(value: "gemma-2b-it", child: Text("Gemma 2B IT")),
                        DropdownMenuItem(value: "phi-2", child: Text("Phi-2")),
                      ],
                      onChanged: (val) => setState(() => selectedModelId = val ?? ""),
                    ),
                    const SizedBox(height: 16),
                    Row(children: [
                      Expanded(child: Text("Context Length: $contextLength tokens")),
                      Slider(
                        value: contextLength.toDouble(),
                        min: 512,
                        max: 8192,
                        divisions: 15,
                        label: "$contextLength",
                        onChanged: (val) => setState(() => contextLength = val.toInt()),
                      ),
                    ]),
                    Row(children: [
                      Expanded(child: Text("Temperature: ${temperature.toStringAsFixed(1)}")),
                      Slider(
                        value: temperature,
                        min: 0.0,
                        max: 2.0,
                        divisions: 20,
                        label: temperature.toStringAsFixed(1),
                        onChanged: (val) => setState(() => temperature = val),
                      ),
                    ]),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),

            // ------------------------------------------------- Privacy Settings
            _sectionTitle(context, "Privacy & Security"),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SwitchListTile(
                      title: const Text("Enable Data Retention"),
                      subtitle: const Text("Store conversations locally"),
                      value: dataRetentionEnabled,
                      onChanged: (val) => setState(() => dataRetentionEnabled = val),
                    ),
                    ListTile(
                      leading: const Icon(Icons.delete_outline, color: AppColors.danger),
                      title: const Text("Clear All Local Data"),
                      subtitle: const Text("Delete conversations, documents, and cached data"),
                      onTap: () => _showClearDataDialog(context),
                    ),
                    if (showEncryptionStatus)
                      ListTile(
                        leading: const Icon(Icons.lock_outline, color: AppColors.success),
                        title: const Text("Encryption Status"),
                        subtitle: const Text("Database encrypted at rest (SQLCipher)"),
                        trailing: const Icon(Icons.check_circle, color: AppColors.success, size: 20),
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),

            // ------------------------------------------------- Search Filters
            _sectionTitle(context, "Search Filters"),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text("Domain Whitelist", style: TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    const Text("Research is restricted to verified government, academic, and legal domains.",
                        style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
                    const SizedBox(height: 12),
                    Wrap(spacing: 8, runSpacing: 8, children: [
                      _domainChip("gov"),
                      _domainChip("edu"),
                      _domainChip("court.gov"),
                      _domainChip("bar.org"),
                      _domainChip("loc.gov"),
                      _domainChip("congress.gov"),
                    ]),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: () {},
                      icon: const Icon(Icons.add, size: 16),
                      label: const Text("Add Domain"),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),

            // ------------------------------------------------- Tool Connections
            _sectionTitle(context, "Tool Connections"),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _toolConnectionTile(
                      provider: "Gmail",
                      icon: Icons.email_outlined,
                      connected: false,
                      onConnect: () => _connectTool(context, "gmail"),
                    ),
                    const Divider(),
                    _toolConnectionTile(
                      provider: "Outlook",
                      icon: Icons.email_outlined,
                      connected: false,
                      onConnect: () => _connectTool(context, "outlook"),
                    ),
                    const Divider(),
                    _toolConnectionTile(
                      provider: "Google Calendar",
                      icon: Icons.calendar_today_outlined,
                      connected: false,
                      onConnect: () => _connectTool(context, "google_calendar"),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),

            // ------------------------------------------------- Appearance
            _sectionTitle(context, "Appearance"),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SegmentedButton<ThemeMode>(
                      segments: const [
                        ButtonSegment(value: ThemeMode.light, label: Text("Light"), icon: const Icon(Icons.light_mode)),
                        ButtonSegment(value: ThemeMode.dark, label: Text("Dark"), icon: const Icon(Icons.dark_mode)),
                        ButtonSegment(value: ThemeMode.system, label: Text("System"), icon: const Icon(Icons.settings_suggest)),
                      ],
                      selected: {appTheme},
                      onSelectionChanged: (set) => setState(() => appTheme = set.first),
                    ),
                    const SizedBox(height: 16),
                    Row(children: [
                      Expanded(child: Text("Font Size: ${fontSize.toStringAsFixed(0)}px")),
                      Slider(
                        value: fontSize,
                        min: 10.0,
                        max: 20.0,
                        divisions: 10,
                        label: "${fontSize.toInt()}",
                        onChanged: (val) => setState(() => fontSize = val),
                      ),
                    ]),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),

            // ------------------------------------------------- Auto-Update
            _sectionTitle(context, "Updates"),
            Card(
              child: SwitchListTile(
                title: const Text("Auto-Update"),
                subtitle: const Text("Automatically check for and install updates"),
                value: autoUpdateEnabled,
                onChanged: (val) => setState(() => autoUpdateEnabled = val),
              ),
            ),
            const SizedBox(height: 32),

            // ------------------------------------------------- About
            _sectionTitle(context, "About"),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text("Counsel AI", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                    const SizedBox(height: 4),
                    const Text("Version 1.0.0", style: TextStyle(color: AppColors.textSecondary)),
                    const SizedBox(height: 16),
                    ListTile(
                      leading: const Icon(Icons.description_outlined),
                      title: const Text("Licenses & Attributions"),
                      onTap: () => _openLicenses(context),
                    ),
                    ListTile(
                      leading: const Icon(Icons.help_outline),
                      title: const Text("Help & Documentation"),
                      onTap: () => _openHelp(context),
                    ),
                    ListTile(
                      leading: const Icon(Icons.bug_report_outlined),
                      title: const Text("Report an Issue"),
                      onTap: () => _reportIssue(context),
                    ),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 40),
            Center(child: Text("Counsel AI MVP · local-first by design", style: Theme.of(context).textTheme.labelSmall)),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(BuildContext context, String title) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Text(title, style: Theme.of(context).textTheme.titleMedium),
      );

  Widget _domainChip(String domain) => Chip(
    avatar: const Icon(Icons.public, size: 14),
    label: Text(domain),
    onDeleted: () {},
    deleteIcon: const Icon(Icons.close, size: 14),
  );

  Widget _toolConnectionTile({
    required String provider,
    required IconData icon,
    required bool connected,
    required VoidCallback onConnect,
  }) => ListTile(
    leading: Icon(icon, color: connected ? AppColors.success : AppColors.textSecondary),
    title: Text(provider),
    subtitle: Text(connected ? "Connected" : "Not connected", 
        style: TextStyle(color: connected ? AppColors.success : AppColors.textSecondary, fontSize: 12)),
    trailing: connected
        ? OutlinedButton(
            onPressed: () {},
            style: OutlinedButton.styleFrom(foregroundColor: AppColors.danger),
            child: const Text("Disconnect"),
          )
        : FilledButton.tonal(onPressed: onConnect, child: const Text("Connect")),
  );

  void _showClearDataDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("Clear All Data?"),
        content: const Text("This will permanently delete all conversations, documents, and cached data. This action cannot be undone."),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("Cancel")),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () {
              // TODO: Implement clear data
              Navigator.pop(ctx);
            },
            child: const Text("Clear"),
          ),
        ],
      ),
    );
  }

  void _connectTool(BuildContext context, String provider) {
    // TODO: Implement OAuth flow
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text("Connecting to $provider... (OAuth flow to be implemented)")),
    );
  }

  void _openLicenses(BuildContext context) {
    // Open licenses page or external URL
    launchUrl(Uri.parse("https://github.com/counsel-ai/counsel-ai/blob/main/docs/LICENSES.md"));
  }

  void _openHelp(BuildContext context) {
    launchUrl(Uri.parse("https://github.com/counsel-ai/counsel-ai/blob/main/docs/USER_MANUAL.md"));
  }

  void _reportIssue(BuildContext context) {
    launchUrl(Uri.parse("https://github.com/counsel-ai/counsel-ai/issues"));
  }
}
