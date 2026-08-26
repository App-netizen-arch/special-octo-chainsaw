import "package:flutter/material.dart";
import "package:provider/provider.dart";

import "../state/app_state.dart";
import "../theme.dart";

/// First-launch wizard: Welcome -> Jurisdiction -> Privacy.
/// "Skip for demo" defaults to United States, California.
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  int step = 0;
  String country = "";
  String province = "";
  final cityController = TextEditingController();
  bool localFirst = true;

  @override
  void initState() {
    super.initState();
    final data =
        context.read<AppState>().jurisdictionData["provinces"] as Map<String, dynamic>? ?? {};
    if (data.isEmpty) return;
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final provinces = (state.jurisdictionData["provinces"] as Map<String, dynamic>?)
            ?.map((k, v) => MapEntry(k, (v as List).cast<String>())) ??
        {};

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text("COUNSEL AI", style: Theme.of(context).textTheme.labelSmall!.copyWith(letterSpacing: 3)),
                const SizedBox(height: 8),
                Expanded(
                  child: SingleChildScrollView(
                    child: ConstrainedBox(
                      constraints: BoxConstraints(minHeight: 380),
                      child: _step(context, state, provinces),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    TextButton(
                      onPressed: () async => context.read<AppState>().skipForDemo(),
                      child: const Text("Skip for demo"),
                    ),
                    Row(children: [
                      if (step > 0)
                        OutlinedButton(
                          onPressed: () => setState(() => step--),
                          child: const Text("Back"),
                        ),
                      const SizedBox(width: 8),
                      FilledButton(
                        onPressed: _canContinue(provinces) ? () => _next(state, provinces) : null,
                        child: Text(step == 2 ? "Start" : "Continue"),
                      ),
                    ]),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  bool _canContinue(Map<String, List<String>> provinces) {
    switch (step) {
      case 1:
        return country.isNotEmpty && province.isNotEmpty;
      default:
        return true;
    }
  }

  void _next(AppState state, Map<String, List<String>> provinces) {
    if (step < 2) {
      setState(() => step++);
      return;
    }
    context.read<AppState>().completeOnboarding(
          country: country,
          province: province,
          city: cityController.text.trim(),
          privacyPreference: localFirst ? "local-first" : "api-ok",
        );
  }

  Widget _step(BuildContext context, AppState state, Map<String, List<String>> provinces) {
    switch (step) {
      case 0:
        return _welcome(context);
      case 1:
        return _jurisdiction(context, provinces);
      default:
        return _privacy(context);
    }
  }

  Widget _welcome(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Text("Your private legal copilot.",
              style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 16),
          _valueRow(Icons.shield_outlined, "Local-first privacy",
              "Run entirely on your machine. Client documents never leave your laptop in Local mode."),
          _valueRow(Icons.travel_explore, "Research with real citations",
              "Deep research restricted to courts, governments and official publishers — sources always attached."),
          _valueRow(Icons.description_outlined, "Drafts you control",
              "Generate NDAs, memos and motions, review them side-by-side, then export."),
        ],
      );

  Widget _valueRow(IconData icon, String title, String subtitle) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.border),
            ),
            child: Icon(icon, size: 20, color: AppColors.accent),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 2),
              Text(subtitle, style: Theme.of(context).textTheme.bodyMedium!.copyWith(color: AppColors.textSecondary)),
            ]),
          ),
        ]),
      );

  Widget _jurisdiction(BuildContext context, Map<String, List<String>> provinces) {
    final countries = provinces.keys.toList();
    final selectedProvinces = provinces[country] ?? <String>[];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SizedBox(height: 24),
      Text("Where do you practise?", style: Theme.of(context).textTheme.headlineMedium),
      const SizedBox(height: 6),
      Text("Answers, citations and templates adapt to your jurisdiction.",
          style: Theme.of(context).textTheme.bodyMedium!.copyWith(color: AppColors.textSecondary)),
      const SizedBox(height: 28),
      _label("Country"),
      DropdownButtonFormField<String>(
        initialValue: country.isEmpty ? null : country,
        items: countries.map((c) => DropdownMenuItem(value: c, child: Text(c))).toList(),
        onChanged: (v) => setState(() {
          country = v ?? "";
          province = "";
        }),
        decoration: const InputDecoration(hintText: "Select a country"),
      ),
      const SizedBox(height: 18),
      _label("Province / State"),
      DropdownButtonFormField<String>(
        initialValue: province.isEmpty ? null : province,
        items: selectedProvinces.map((p) => DropdownMenuItem(value: p, child: Text(p))).toList(),
        onChanged: (v) => setState(() => province = v ?? ""),
        decoration: InputDecoration(hintText: country.isEmpty ? "Pick a country first" : "Select"),
      ),
      const SizedBox(height: 18),
      _label("City (optional)"),
      TextField(controller: cityController, decoration: const InputDecoration(hintText: "e.g. San Francisco")),
    ]);
  }

  Widget _privacy(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SizedBox(height: 24),
        Text("Privacy preference", style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 20),
        _privacyCard(
          selected: localFirst,
          title: "Local-first",
          description: "Use the on-device model by default. Documents stay on this machine. You will be asked before any external call.",
          onTap: () => setState(() => localFirst = true),
        ),
        const SizedBox(height: 12),
        _privacyCard(
          selected: !localFirst,
          title: "Allow API mode",
          description: "Permit cloud models (DeepSeek/OpenAI-compatible) when chosen. A persistent banner shows whenever data would leave this device.",
          onTap: () => setState(() => localFirst = false),
        ),
      ]);

  Widget _privacyCard({required bool selected, required String title, required String description, required VoidCallback onTap}) =>
      InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            border: Border.all(color: selected ? AppColors.accent : AppColors.border, width: selected ? 1.5 : 1),
            borderRadius: BorderRadius.circular(12),
            color: selected ? AppColors.surface : AppColors.background,
          ),
          child: Row(children: [
            Icon(selected ? Icons.check_circle : Icons.radio_button_unchecked,
                color: selected ? AppColors.accent : AppColors.textSecondary),
            const SizedBox(width: 14),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text(description, style: Theme.of(context).textTheme.bodySmall!.copyWith(color: AppColors.textSecondary)),
            ])),
          ]),
        ),
      );

  Widget _label(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text(text, style: Theme.of(context).textTheme.labelSmall),
      );
}
