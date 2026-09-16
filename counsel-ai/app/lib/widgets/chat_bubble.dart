import "dart:async";

import "package:flutter/material.dart";
import "package:flutter_markdown/flutter_markdown.dart";

import "../models/models.dart";
import "../state/app_state.dart" show ResearchProgress;
import "../theme.dart";
import "citation_card.dart";

class ChatBubble extends StatefulWidget {
  const ChatBubble({super.key, required this.message, this.researchProgress});

  final Message message;
  final ResearchProgress? researchProgress;

  @override
  State<ChatBubble> createState() => _ChatBubbleState();
}

class _ChatBubbleState extends State<ChatBubble> {
  bool _caretOn = true;
  Timer? _caretTimer;

  @override
  void initState() {
    super.initState();
    _caretTimer = Timer.periodic(const Duration(milliseconds: 500), (_) {
      if (mounted && widget.message.streaming) setState(() => _caretOn = !_caretOn);
    });
  }

  @override
  void dispose() {
    _caretTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isUser = widget.message.role == "user";
    final width = MediaQuery.sizeOf(context).width;
    final maxWidth = isUser ? width.clamp(0, 760) * 0.78 : width.clamp(0, 920) * 0.9;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth.toDouble()),
        child: Padding(
          padding: EdgeInsets.only(top: 7, bottom: 7, left: isUser ? 32 : 0, right: isUser ? 0 : 20),
          child: isUser ? _user(context) : _assistant(context),
        ),
      ),
    );
  }

  Widget _user(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.border),
      ),
      child: SelectableText(widget.message.content, style: Theme.of(context).textTheme.bodyMedium),
    );
  }

  Widget _assistant(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (widget.message.isError)
        Padding(
          padding: const EdgeInsets.only(bottom: 7),
          child: Row(children: [
            const Icon(Icons.info_outline, size: 15, color: AppColors.danger),
            const SizedBox(width: 6),
            Text("Something needs your attention",
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.danger)),
          ]),
        ),
      _body(context),
      if (widget.researchProgress != null && widget.message.streaming) _researchSteps(),
      if (widget.message.sources.isNotEmpty) ...[
        const SizedBox(height: 8),
        CitationCard(sources: widget.message.sources),
      ],
    ]);
  }

  Widget _body(BuildContext context) {
    final text = widget.message.content;
    if (text.isEmpty && widget.message.streaming) {
      return Text(
        widget.researchProgress != null ? "Researching…" : "Thinking…",
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary),
      );
    }
    if (widget.message.isError) {
      return SelectableText(text, style: Theme.of(context).textTheme.bodyMedium);
    }
    return MarkdownBody(
      data: text + (widget.message.streaming && _caretOn ? " ▍" : ""),
      selectable: true,
      styleSheet: MarkdownStyleSheet(
        p: Theme.of(context).textTheme.bodyMedium!,
        h1: Theme.of(context).textTheme.titleLarge!,
        h2: Theme.of(context).textTheme.titleMedium!,
        h3: Theme.of(context).textTheme.titleMedium!,
        listBullet: Theme.of(context).textTheme.bodyMedium!,
        blockquoteDecoration: const BoxDecoration(
          border: Border(left: BorderSide(color: AppColors.border, width: 3)),
        ),
        codeblockDecoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(8)),
        code: AppTheme.mono(),
        horizontalRuleDecoration: const BoxDecoration(
          border: Border(top: BorderSide(color: AppColors.border)),
        ),
      ),
    );
  }

  Widget _researchSteps() {
    final rp = widget.researchProgress!;
    const stages = [
      ("Planning", ResearchStage.planning),
      ("Searching legitimate sources", ResearchStage.searching),
      ("Reading", ResearchStage.reading),
      ("Writing", ResearchStage.writing),
    ];
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        for (final (label, key) in stages)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(children: [
              Icon(
                rp.completedStages.contains(key)
                    ? Icons.check_circle
                    : (rp.stage == key ? Icons.radio_button_checked : Icons.radio_button_off),
                size: 14,
                color: rp.completedStages.contains(key) ? AppColors.success : AppColors.textSecondary,
              ),
              const SizedBox(width: 8),
              Text(label, style: const TextStyle(fontSize: 12.5, color: AppColors.textSecondary)),
            ]),
          ),
      ]),
    );
  }
}
