import "package:file_picker/file_picker.dart";
import "package:flutter/material.dart";
import "package:provider/provider.dart";

import "../services/export_utils.dart";
import "../state/app_state.dart";
import "../theme.dart";
import "../widgets/mdx_preview.dart";

/// Split view: raw MDX (editable, left) | rendered serif preview (right).
/// The divider is draggable; rendering updates live while tokens stream.
class DocumentScreen extends StatefulWidget {
  const DocumentScreen({super.key});

  @override
  State<DocumentScreen> createState() => _DocumentScreenState();
}

class _DocumentScreenState extends State<DocumentScreen> {
  late TextEditingController editor;

  @override
  void initState() {
    super.initState();
    editor = TextEditingController(text: context.read<AppState>().mdxText);
  }

  @override
  void dispose() {
    editor.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    // keep the raw pane in sync while tokens stream in from the backend
    if (state.isStreaming && state.mdxText.isNotEmpty && state.mdxText != editor.text) {
      editor.text = state.mdxText;
      editor.selection = TextSelection.collapsed(offset: editor.text.length);
    }

    return Column(children: [
      _toolbar(context, state),
      Expanded(
        child: LayoutBuilder(builder: (context, constraints) {
          final split =
              (constraints.maxWidth * state.docSplitRatio).clamp(260.0, constraints.maxWidth - 280);
          return Row(children: [
            SizedBox(
              width: split,
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                _paneHeader(context, "RAW MDX"),
                Expanded(
                  child: TextField(
                    controller: editor,
                    maxLines: null,
                    expands: true,
                    style: AppTheme.mono().copyWith(fontSize: 12.5, height: 1.55, color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      isDense: true,
                      filled: false,
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.symmetric(horizontal: 18, vertical: 16),
                    ),
                    onChanged: (v) => state.updateMdxText(v),
                  ),
                ),
              ]),
            ),
            _DragHandle(
              onDrag: (dx) => state.setDocSplitRatio(((split + dx) / constraints.maxWidth)),
            ),
            Expanded(
              child: Container(color: Colors.white, child: MdxPreview(mdx: editor.text)),
            ),
          ]);
        }),
      ),
    ]);
  }

  Widget _toolbar(BuildContext context, AppState state) {
    return Container(
      height: 52,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(children: [
        Text("Document", style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(width: 24),
        for (final t in const ["nda", "employment_contract", "legal_memo", "motion", "letter"])
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ActionChip(
              label: Text(_templateLabel(t), style: const TextStyle(fontSize: 12)),
              backgroundColor: Colors.white,
              side: const BorderSide(color: AppColors.border),
              onPressed: () async {
                await state.send("", templateKey: t);
              },
            ),
          ),
        const Spacer(),
        OutlinedButton.icon(
            onPressed: () => _export(context, state, ExportFormat.mdx),
            icon: const Icon(Icons.copy, size: 15),
            label: const Text("Copy MDX")),
        const SizedBox(width: 8),
        OutlinedButton.icon(
            onPressed: () => _export(context, state, ExportFormat.docx),
            icon: const Icon(Icons.description_outlined, size: 15),
            label: const Text(".docx")),
        const SizedBox(width: 8),
        FilledButton.icon(
            onPressed: () => _export(context, state, ExportFormat.pdf),
            icon: const Icon(Icons.picture_as_pdf_outlined, size: 15),
            label: const Text(".pdf")),
      ]),
    );
  }

  String _templateLabel(String key) => switch (key) {
        "nda" => "NDA",
        "employment_contract" => "Employment Contract",
        "legal_memo" => "Legal Memo",
        "motion" => "Motion",
        "letter" => "Letter",
        _ => key,
      };

  Future<void> _export(BuildContext context, AppState state, ExportFormat fmt) async {
    final mdx = state.mdxText.trim();
    if (mdx.isEmpty) {
      ScaffoldMessenger.of(this.context).showSnackBar(const SnackBar(content: Text("Nothing to export yet.")));
      return;
    }
    if (fmt == ExportFormat.mdx) {
      await copyToClipboard(mdx);
      if (!mounted) return;
      ScaffoldMessenger.of(this.context).showSnackBar(const SnackBar(content: Text("MDX copied to clipboard.")));
      return;
    }
    String? path;
    if (fmt == ExportFormat.docx) {
      path = await FilePicker.platform.saveFile(
          fileName: suggestedName(fmt), type: FileType.custom, allowedExtensions: ["docx"]);
      if (path == null) return;
      try {
        final bytes = buildMinimalDocx(mdx);
        FileSaver.save(path, bytes);
      } catch (_) {
        if (!mounted) return;
        ScaffoldMessenger.of(this.context)
            .showSnackBar(const SnackBar(content: Text("Could not write the .docx file.")));
        return;
      }
    } else {
      path = await FilePicker.platform.saveFile(
          fileName: suggestedName(fmt), type: FileType.custom, allowedExtensions: ["pdf"]);
      if (path == null) return;
      try {
        final bytes = await buildPdfBytes(mdx);
        FileSaver.save(path, bytes);
      } catch (_) {
        if (!mounted) return;
        ScaffoldMessenger.of(this.context)
            .showSnackBar(const SnackBar(content: Text("Could not write the .pdf file.")));
        return;
      }
    }
    if (!mounted) return;
    ScaffoldMessenger.of(this.context).showSnackBar(SnackBar(content: Text("Saved to $path")));
  }
}

Widget _paneHeader(BuildContext context, String label) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
      decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: AppColors.border))),
      child: Text(label, style: Theme.of(context).textTheme.labelSmall!.copyWith(letterSpacing: 1.2)),
    );

class _DragHandle extends StatelessWidget {
  const _DragHandle({required this.onDrag});

  final ValueChanged<double> onDrag;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onHorizontalDragUpdate: (d) => onDrag(d.delta.dx),
      child: MouseRegion(
        cursor: SystemMouseCursors.resizeColumn,
        child: Container(width: 6, color: AppColors.border),
      ),
    );
  }
}
