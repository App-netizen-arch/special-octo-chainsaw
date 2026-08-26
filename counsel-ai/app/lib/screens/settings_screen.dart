import "package:flutter/material.dart";
import "package:provider/provider.dart";

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

            // -------------------------------------------------- whitelist
            _sectionTitle(context, "Legitimate sources"),
            Text("Research results are restricted server-side to government, academic, court, bar-association and official publisher domains.",
                style: Theme.of(context).textTheme.bodySmall!.copyWith(color: AppColors.textSecondary)),

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
}
