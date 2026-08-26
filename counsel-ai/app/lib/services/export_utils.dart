import "dart:convert";
import "dart:io";

import "package:archive/archive.dart";
import "package:flutter/services.dart" show Clipboard, ClipboardData;
import "package:pdf/widgets.dart" as pw;

/// Export helpers for the document view: MDX copy, minimal .docx, .pdf.

enum ExportFormat { mdx, docx, pdf }

Future<void> copyToClipboard(String text) => Clipboard.setData(ClipboardData(text: text));

String suggestedName(ExportFormat fmt) => "counsel-draft.${fmt.name}";

// --------------------------------------------------------------------- docx
// A .docx file is a ZIP of XML parts. We build a minimal, valid OOXML
// document with one paragraph per markdown block line. This avoids relying
// on third-party docx packages for a robust desktop MVP.

String _escapeXml(String s) => s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

List<int> buildMinimalDocx(String mdx) {
  final buffer = StringBuffer();
  final lines = const LineSplitter().convert(_stripMarkdownToText(mdx));
  for (final line in lines) {
    if (line.trim().isEmpty) continue;
    buffer.write(
        '<w:p><w:pPr><w:spacing w:after="160"/></w:pPr>'
        '<w:r><w:rPr><w:sz w:val="24"/></w:rPr>'
        '<w:t xml:space="preserve">${_escapeXml(line)}</w:t></w:r></w:p>');
  }
  final body = buffer.toString();

  final archive = Archive();
  void addPart(String path, String content) {
    final bytes = utf8.encode(content);
    archive.addFile(ArchiveFile(path, bytes.length, bytes));
  }

  const contentTypes =
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
      '</Types>';
  const rels =
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
      '</Relationships>';
  final document =
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
      '<w:body>$body'
      '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
      '</w:body></w:document>';

  addPart("[Content_Types].xml", contentTypes);
  addPart("_rels/.rels", rels);
  addPart("word/document.xml", document);

  return ZipEncoder().encode(archive)!;
}

String _stripMarkdownToText(String mdx) {
  var out = mdx.replaceFirst(RegExp(r"^export const frontmatter[\s\S]*?^\}\s*$", multiLine: true), "");
  // light markdown cleanup for word processors
  out = out.replaceAllMapped(RegExp(r"^#{1,6}\s+", multiLine: true), (m) => "");
  out = out.replaceAll("**", "").replaceAll("*", "").replaceAll("`", "");
  out = out.replaceAll(RegExp(r"\|"), " ");
  return out.trim();
}

// ---------------------------------------------------------------------- pdf

Future<List<int>> buildPdfBytes(String mdx) async {
  final doc = pw.Document();
  final blocks = <pw.Widget>[];
  final lines = const LineSplitter().convert(mdx);
  for (final raw in lines) {
    final line = raw.trimRight();
    if (line.startsWith("# ")) {
      blocks.add(pw.Padding(
          padding: const pw.EdgeInsets.only(top: 14, bottom: 6),
          child: pw.Text(line.substring(2),
              style: pw.TextStyle(fontSize: 20, fontWeight: pw.FontWeight.bold))));
    } else if (line.startsWith("## ")) {
      blocks.add(pw.Padding(
          padding: const pw.EdgeInsets.only(top: 10, bottom: 4),
          child: pw.Text(line.substring(3),
              style: pw.TextStyle(fontSize: 15, fontWeight: pw.FontWeight.bold))));
    } else if (line.startsWith("---")) {
      blocks.add(pw.Padding(padding: const pw.EdgeInsets.symmetric(vertical: 8), child: pw.Divider()));
    } else if (line.trim().isEmpty) {
      continue;
    } else {
      blocks.add(pw.Padding(
          padding: const pw.EdgeInsets.only(bottom: 5),
          child: pw.Text(_cleanInline(line), style: const pw.TextStyle(fontSize: 11))));
    }
  }
  doc.addPage(pw.MultiPage(build: (context) => blocks));
  return doc.save();
}

String _cleanInline(String s) => s
    .replaceAll("**", "")
    .replaceAll("*", "")
    .replaceAll("`", "")
    .replaceAll(RegExp(r"\[([^\]]*)\]\(([^)]*)\)"), "\$1");

/// Writes bytes to disk; isolated so UI code stays dart:io-free.
class FileSaver {
  static void save(String path, List<int> bytes) {
    File(path).writeAsBytesSync(bytes);
  }
}
