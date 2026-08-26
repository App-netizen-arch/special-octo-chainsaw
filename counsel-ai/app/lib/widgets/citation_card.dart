import "package:flutter/material.dart";

import "../models/models.dart";
import "../theme.dart";

/// Citation card shown beneath AI answers — sources always visible.
/// Citations render in 12px monospace per the design spec.
class CitationCard extends StatelessWidget {
  const CitationCard({super.key, required this.sources});

  final List<Source> sources;

  @override
  Widget build(BuildContext context) {
    if (sources.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(sources.first.isDocument ? Icons.description_outlined : Icons.link,
              size: 14, color: AppColors.textSecondary),
          const SizedBox(width: 6),
          Text("SOURCES", style: Theme.of(context).textTheme.labelSmall!.copyWith(letterSpacing: 1.2)),
        ]),
        const SizedBox(height: 8),
        ...sources.take(8).map(_row),
      ]),
    );
  }

  Widget _row(Source s) {
    final relevance = s.relevance > 0 ? "   ${(s.relevance * 100).clamp(1, 100).toStringAsFixed(0)}%" : "";
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(
          "${s.citationLabel}$relevance",
          style: AppTheme.mono().copyWith(fontWeight: FontWeight.w600, color: AppColors.textPrimary),
        ),
        if (s.snippet.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 12, top: 2),
            child: SelectableText("\"${s.snippet}\"", maxLines: 2,
                style: AppTheme.mono()),
          ),
      ]),
    );
  }
}
