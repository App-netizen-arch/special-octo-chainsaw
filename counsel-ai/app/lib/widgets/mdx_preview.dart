import "package:flutter/material.dart";
import "package:flutter_markdown/flutter_markdown.dart";

import "../theme.dart";

/// Rendered MDX preview (right pane of the document view).
/// Frontmatter `export const frontmatter = {...}` blocks are hidden; the rest
/// is rendered as a legal document in serif with generous margins.
class MdxPreview extends StatelessWidget {
  const MdxPreview({super.key, required this.mdx});

  final String mdx;

  @override
  Widget build(BuildContext context) {
    final body = _stripFrontmatter(mdx);
    if (body.trim().isEmpty) {
      return Center(child: Text("Nothing to preview yet.", style: TextStyle(color: AppColors.textSecondary)));
    }
    return Markdown(
      data: body,
      selectable: true,
      padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 36),
      styleSheet: MarkdownStyleSheet(
        p: AppTheme.document(),
        h1: AppTheme.document(size: 24, weight: FontWeight.w700),
        h2: AppTheme.document(size: 17, weight: FontWeight.w600),
        h3: AppTheme.document(size: 15.5, weight: FontWeight.w600),
        h1Padding: const EdgeInsets.only(bottom: 12),
        h2Padding: const EdgeInsets.only(top: 18, bottom: 6),
        listBullet: AppTheme.document(),
        blockquote: AppTheme.document().copyWith(fontStyle: FontStyle.italic, color: AppColors.textSecondary),
        blockquoteDecoration: BoxDecoration(border: Border(left: BorderSide(color: AppColors.border, width: 3))),
        tableHead: AppTheme.document(weight: FontWeight.w600),
        tableBody: AppTheme.document(size: 14),
        tableBorder: TableBorder.all(color: AppColors.border, width: 0.8),
        code: AppTheme.mono(),
        codeblockDecoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(8)),
        horizontalRuleDecoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.border))),
      ),
    );
  }

  /// Hides the MDX frontmatter export so the preview reads like the filed
  /// document (the raw pane still shows it — same component model as MDX,
  /// where exports are metadata, not content).
  String _stripFrontmatter(String src) {
    final exportPattern = RegExp(r"^export const frontmatter[\s\S]*?^\}\s*$", multiLine: true);
    return src.replaceFirst(exportPattern, "").trim();
  }
}
