import "dart:async";

import "package:flutter/material.dart";
import "package:flutter_markdown/flutter_markdown.dart";

import "../models/models.dart";
import "../state/app_state.dart" show ResearchProgress;
import "../theme.dart";
import "citation_card.dart";

/// A single chat turn. User messages right, AI messages left (spec 4.2).
class ChatBubble extends StatefulWidget {
  const ChatBubble({
    super.key,
    required this.message,
    this.researchProgress,
  });

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
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.72),
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: isUser ? AppColors.surface : AppColors.background,
          border: Border.all(color: isUser ? Colors.transparent : AppColors.border),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (!isUser && widget.message.isError)
            Row(children: [
              Icon(Icons.info_outline, size: 15, color: AppColors.danger),
              const SizedBox(width: 6),
              Text("Something needs your attention", style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.danger)),
            ]),
          if (!isUser && widget.message.isError) const SizedBox(height: 6),
          _body(context, isUser),
          if (!isUser) ...[
            if (widget.researchProgress != null && widget.message.streaming)
              _researchSteps(),
            CitationCard(sources: widget.message.sources),
          ],
        ]),
      ),
    );
  }

  Widget _body(BuildContext context, bool isUser) {
    final text = widget.message.content;
    if (text.isEmpty && widget.message.streaming) {
      return Text(widget.researchProgress != null ? "Researching…" : "Thinking…",
          style: TextStyle(color: AppColors.textSecondary));
    }
    if (isUser || widget.message.isError) {
      return SelectableText(text, style: Theme.of(context).textTheme.bodyMedium!.copyWith(color: widget.message.isError ? AppColors.textPrimary : AppColors.textPrimary));
    }
    // AI answers render as markdown; a subtle caret follows while streaming.
    return MarkdownBody(
      data: text + (widget.message.streaming && _caretOn ? " ▍" : ""),
      selectable: true,
      styleSheet: MarkdownStyleSheet(
        p: Theme.of(context).textTheme.bodyMedium!,
        h1: Theme.of(context).textTheme.titleLarge!,
        h2: Theme.of(context).textTheme.titleMedium!,
        h3: Theme.of(context).textTheme.titleMedium!,
        listBullet: Theme.of(context).textTheme.bodyMedium!,
        blockquoteDecoration: BoxDecoration(
          border: Border(left: BorderSide(color: AppColors.border, width: 3)),
        ),
        codeblockDecoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(8),
        ),
        code: AppTheme.mono(),
        horizontalRuleDecoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.border))),
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
              Text(label, style: TextStyle(fontSize: 12.5, color: AppColors.textSecondary)),
            ]),
          ),
      ]),
    );
  }
}
