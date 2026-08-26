import "package:file_picker/file_picker.dart";
import "package:flutter/material.dart";
import "package:flutter/services.dart";
import "package:provider/provider.dart";

import "../models/models.dart";
import "../state/app_state.dart";
import "../theme.dart";
import "../widgets/chat_bubble.dart";
import "../widgets/consent_dialog.dart";
import "../widgets/mode_selector.dart";

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final controller = TextEditingController();
  final scrollController = ScrollController();
  bool _draftIntent = false;

  static const examples = ["Limitation periods", "Repudiatory breach", "Draft an NDA"];

  @override
  void dispose() {
    controller.dispose();
    scrollController.dispose();
    super.dispose();
  }

  void _send(AppState state, {String? overrideText, String? templateKey}) {
    final text = overrideText ?? controller.text.trim();
    if (text.isEmpty && templateKey == null) return;
    final asMdx = state.mode != ChatMode.research &&
        state.mode != ChatMode.tools &&
        (_draftIntent || _looksLikeDraft(text));
    if (asMdx && text.isNotEmpty) {
      state.setView(MainView.document);
    }
    if (templateKey != null && text.isEmpty) {
      // Template chip: instant skeleton into the document view.
      state.setView(MainView.document);
      state.send("", templateKey: templateKey);
      return;
    }
    controller.clear();
    setState(() => _draftIntent = false);
    state.send(text, asMdx: asMdx);
  }

  static final RegExp _draftRe =
      RegExp(r"\b(draft|prepare|write|generate)\b.*\b(nda|contract|agreement|memo|memorandum|motion|letter|document)\b",
          caseSensitive: false);

  static bool _looksLikeDraft(String t) => _draftRe.hasMatch(t);

  Future<void> _attach(AppState state) async {
    final res = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ["pdf", "docx", "txt"],
    );
    final path = res?.files.single.path;
    if (path == null || !mounted) return;
    final err = await state.uploadDocument(path, res!.files.single.name);
    if (!mounted) return;
    if (err != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err)));
    }
  }

  Future<void> _runToolFlow(BuildContext context, AppState state) async {
    final tools = state.tools;
    if (tools.isEmpty) return;
    final slug = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text("Choose an action", style: Theme.of(context).textTheme.titleMedium),
        content: SizedBox(
          width: 380,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            for (final t in tools)
              ListTile(
                dense: true,
                leading: Icon(t.slug == "SAVE_NOTE" ? Icons.save_outlined : Icons.send_outlined,
                    size: 18, color: t.requiresExternalSend ? AppColors.privacyTool : AppColors.success),
                title: Text(t.name, style: const TextStyle(fontSize: 14)),
                subtitle: Text(t.description, maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall),
                onTap: () => Navigator.pop(context, t.slug),
              ),
          ]),
        ),
      ),
    );
    if (slug == null || !mounted) return;

    // MVP stub inputs are prefilled from the last AI answer or typed by the user.
    final input = await showDialog<Map<String, dynamic>>(
      context: this.context,
      builder: (context) => _ToolInputDialog(slug: slug),
    );
    if (input == null || !mounted) return;

    try {
      final preview = await state.previewTool(slug, input);
      final requiresConsent = (preview["requires_external_send"] as bool?) ?? true;
      var confirmed = false;
      String? previewText;
      if (requiresConsent) {
        previewText = _formatPreview(preview);
        if (!mounted) return;
        confirmed = await showConsentDialog(this.context, toolName: slug, previewText: previewText);
        if (!confirmed || !mounted) return;
      }
      final err = await state.executeTool(slug, input, confirmed: confirmed);
      if (!mounted) return;
      if (err.isNotEmpty) {
        state.pushLocalMessage(Message.assistant(err, state.mode, isError: true));
      } else {
        state.pushLocalMessage(Message.assistant(
            "${_toolDoneLine(slug)}\n\n```json\n${state.lastToolResult}\n```", state.mode));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(this.context)
            .showSnackBar(const SnackBar(content: Text("The action could not be completed.")));
      }
    }
  }

  String _formatPreview(Map<String, dynamic> preview) {
    final fields = (preview["fields"] as Map?)?.cast<String, dynamic>() ?? {};
    return fields.entries.map((e) => "${e.key}: ${e.value}").join("\n");
  }

  String _toolDoneLine(String slug) {
    switch (slug) {
      case "DRAFT_EMAIL":
        return "Email drafted locally (simulated — nothing was sent).";
      case "CREATE_CALENDAR_EVENT":
        return "Calendar event created as a local .ics file (simulated).";
      default:
        return "Saved on this machine.";
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final showEmpty = state.messages.isEmpty;

    return Column(children: [
      Expanded(
        child: showEmpty
            ? _emptyState(context, state)
            : NotificationListener<ScrollNotification>(
                onNotification: (_) {
                  return false;
                },
                child: ListView.builder(
                  controller: scrollController,
                  padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 20),
                  itemCount: state.messages.length,
                  itemBuilder: (context, i) => ChatBubble(
                    message: state.messages[i],
                    researchProgress:
                        state.messages[i].streaming && state.mode == ChatMode.research ? state.research : null,
                  ),
                ),
              ),
      ),
      if (state.mode == ChatMode.tools) _toolsBar(context, state),
      _inputBar(context, state),
    ]);
  }

  // ------------------------------------------------------------------ empty

  Widget _emptyState(BuildContext context, AppState state) {
    final isResearch = state.mode == ChatMode.research;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(isResearch ? "LEGAL RESEARCH" : "PRIVATE LEGAL RESEARCH",
                style: Theme.of(context).textTheme.labelSmall!.copyWith(letterSpacing: 2)),
            const SizedBox(height: 10),
            Text("What do you want to know?", style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 8),
            Text("Ask a legal question, research a topic, or draft something you can review.",
                style: Theme.of(context).textTheme.bodyMedium!.copyWith(color: AppColors.textSecondary)),
            const SizedBox(height: 28),
            Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              _card(context, Icons.travel_explore, "Research anything",
                  "Search legitimate legal sources and keep citations attached to every answer.",
                  onTap: () { state.setMode(ChatMode.research); }),
              const SizedBox(width: 14),
              _card(context, Icons.edit_note, "Draft a document",
                  "Start from a familiar legal template and review it before use.",
                  onTap: () { state.setView(MainView.document); }),
            ]),
            const SizedBox(height: 22),
            Wrap(spacing: 10, children: [
              for (final e in examples)
                ActionChip(
                  label: Text(e, style: const TextStyle(fontSize: 13)),
                  backgroundColor: Colors.white,
                  side: const BorderSide(color: AppColors.border),
                  onPressed: () {
                    if (e == "Limitation periods") {
                      state.setMode(ChatMode.research);
                      _send(state, overrideText: "What are the limitation periods for breach of contract?");
                    } else if (e == "Repudiatory breach") {
                      state.setMode(ChatMode.research);
                      _send(state, overrideText: "Explain repudiatory breach and its consequences.");
                    } else {
                      _send(state, templateKey: "nda");
                    }
                  },
                ),
            ]),
          ]),
        ),
      ),
    );
  }

  Widget _card(BuildContext context, IconData icon, String title, String subtitle, {required VoidCallback onTap}) =>
      Expanded(
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              border: Border.all(color: AppColors.border),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Icon(icon, size: 17, color: AppColors.accent),
                const SizedBox(width: 8),
                Text(title, style: Theme.of(context).textTheme.titleMedium),
              ]),
              const SizedBox(height: 6),
              Text(subtitle, style: Theme.of(context).textTheme.bodySmall!.copyWith(color: AppColors.textSecondary)),
            ]),
          ),
        ),
      );

  // -------------------------------------------------------------- tools bar

  Widget _toolsBar(BuildContext context, AppState state) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(40, 0, 40, 4),
      child: Row(children: [
        OutlinedButton.icon(
          onPressed: () => _runToolFlow(context, state),
          icon: const Icon(Icons.bolt_outlined, size: 16),
          label: const Text("Run an action"),
        ),
        const SizedBox(width: 10),
        Text("Actions are simulated in this MVP; nothing leaves your machine without consent.",
            style: Theme.of(context).textTheme.bodySmall!.copyWith(color: AppColors.textSecondary)),
      ]),
    );
  }

  // -------------------------------------------------------------- input bar

  Widget _inputBar(BuildContext context, AppState state) {
    final attachedDocs = state.documents.where((d) => state.attachedDocIds.contains(d.id)).toList();
    return Container(
      decoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.border))),
      padding: const EdgeInsets.fromLTRB(40, 12, 40, 16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (attachedDocs.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Wrap(spacing: 8, children: [
              for (final d in attachedDocs)
                InputChip(
                  backgroundColor: Colors.white,
                  label: Text("${d.name} (${d.pages}p)", style: const TextStyle(fontSize: 12)),
                  deleteIcon: const Icon(Icons.close, size: 14),
                  onDeleted: () => state.toggleAttachment(d.id),
                  onPressed: () => state.toggleAttachment(d.id),
                ),
            ]),
          ),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          IconButton(
            tooltip: "Attach PDF/DOCX/TXT",
            onPressed: () => _attach(state),
            icon: const Icon(Icons.attach_file, size: 19, color: AppColors.textSecondary),
          ),
          Expanded(
            child: CallbackShortcuts(
              bindings: {
                const SingleActivator(LogicalKeyboardKey.enter): () => _send(state),
              },
              child: TextField(
                controller: controller,
                maxLines: null,
                minLines: 1,
                textInputAction: TextInputAction.newline,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  hintText: switch (state.mode) {
                    ChatMode.research => "Research a legal question…",
                    ChatMode.tools => "Describe the action, then run it below…",
                    ChatMode.api => "Ask anything (API mode)…",
                    ChatMode.local => "Ask anything (stays on this machine)…",
                  },
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          _sendButton(context, state),
        ]),
        const SizedBox(height: 6),
        Center(child: ModeSelector(current: state.mode, onChanged: (m) => state.setMode(m))),
      ]),
    );
  }

  Widget _sendButton(BuildContext context, AppState state) {
    final enabled = controller.text.trim().isNotEmpty && !state.isStreaming;
    return Tooltip(
      message: state.isStreaming ? "Working…" : "Send (Enter)",
      child: GestureDetector(
        onTap: enabled ? () => _send(state) : null,
        child: Container(
          height: 42,
          width: 42,
          decoration: BoxDecoration(
            color: enabled ? AppColors.accent : AppColors.surface,
            shape: BoxShape.circle,
            border: Border.all(color: enabled ? Colors.transparent : AppColors.border),
          ),
          child: state.isStreaming
              ? const Padding(padding: EdgeInsets.all(11), child: CircularProgressIndicator(strokeWidth: 2))
              : Icon(Icons.arrow_upward, size: 18, color: enabled ? Colors.white : AppColors.textSecondary),
        ),
      ),
    );
  }
}

class _ToolInputDialog extends StatefulWidget {
  const _ToolInputDialog({required this.slug});
  final String slug;

  @override
  State<_ToolInputDialog> createState() => _ToolInputDialogState();
}

class _ToolInputDialogState extends State<_ToolInputDialog> {
  late final Map<String, TextEditingController> controllers;
  DateTime date = DateTime.now();

  @override
  void initState() {
    super.initState();
    final isEmail = widget.slug == "DRAFT_EMAIL";
    controllers = {
      if (isEmail) "to": TextEditingController(),
      if (isEmail) "subject": TextEditingController(),
      if (isEmail) "body": TextEditingController(),
      if (!isEmail) "title": TextEditingController(),
      if (!isEmail) "time": TextEditingController(text: "09:00"),
    };
  }

  @override
  void dispose() {
    for (final c in controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEvent = widget.slug == "CREATE_CALENDAR_EVENT";
    return AlertDialog(
      title: Text(isEvent ? "New calendar event" : widget.slug == "DRAFT_EMAIL" ? "Draft email" : "Save note",
          style: Theme.of(context).textTheme.titleMedium),
      content: SizedBox(
        width: 420,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (isEvent) ...[
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.event, size: 18),
              title: Text("${date.year}-${date.month.toString().padLeft(2, "0")}-${date.day.toString().padLeft(2, "0")}"),
              trailing: const Icon(Icons.calendar_today, size: 16),
              onTap: () async {
                final d = await showDatePicker(
                    context: context, firstDate: DateTime(2020), lastDate: DateTime(2100), initialDate: date);
                if (d != null) setState(() => date = d);
              },
            ),
          ],
          for (final e in controllers.entries)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: TextField(
                controller: e.value,
                maxLines: e.key == "body" ? 5 : 1,
                decoration: InputDecoration(hintText: _hint(e.key)),
              ),
            ),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text("Cancel")),
        FilledButton(onPressed: _submit, child: const Text("Continue")),
      ],
    );
  }

  String _hint(String key) => switch (key) {
        "to" => "Recipient email",
        "subject" => "Subject",
        "body" => "Message body",
        "title" => "Title",
        "time" => "Start time (HH:MM)",
        _ => key,
      };

  void _submit() {
    final out = <String, dynamic>{};
    controllers.forEach((k, c) => out[k] = c.text.trim());
    if (widget.slug == "DRAFT_EMAIL") {
      if ((out["to"] ?? "").isEmpty || (out["body"] ?? "").isEmpty) return;
    } else if (widget.slug == "CREATE_CALENDAR_EVENT") {
      if ((out["title"] ?? "").isEmpty) return;
      out["date"] = "${date.year}-${date.month.toString().padLeft(2, "0")}-${date.day.toString().padLeft(2, "0")}";
      out["duration_minutes"] = 60;
    } else {
      out["content_markdown"] = "# ${out["title"]}\n\n(Add note content.)";
    }
    Navigator.pop(context, out);
  }
}
