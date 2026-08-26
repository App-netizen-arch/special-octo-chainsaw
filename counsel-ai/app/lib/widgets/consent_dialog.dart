import "package:flutter/material.dart";

import "../theme.dart";

/// Consent modal required before any tool action that sends data externally
/// (spec 4.6). Returns true only when the user explicitly presses Send.
Future<bool> showConsentDialog(BuildContext context,
    {required String toolName, String? previewText}) async {
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (context) => AlertDialog(
      backgroundColor: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: const BorderSide(color: AppColors.border)),
      title: Row(children: [
        Icon(Icons.shield_outlined, color: AppColors.privacyTool, size: 20),
        const SizedBox(width: 8),
        Text("External action", style: Theme.of(context).textTheme.titleMedium),
      ]),
      content: SizedBox(
        width: 460,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text("This action will send data externally.",
              style: Theme.of(context).textTheme.bodyMedium!.copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          Text("Review what will be shared before continuing.",
              style: Theme.of(context).textTheme.bodySmall!.copyWith(color: AppColors.textSecondary)),
          if (previewText != null && previewText.isNotEmpty) ...[
            const SizedBox(height: 14),
            Container(
              width: double.infinity,
              constraints: const BoxConstraints(maxHeight: 220),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.border),
              ),
              child: SingleChildScrollView(child: SelectableText(previewText, style: AppTheme.mono())),
            ),
          ],
        ]),
      ),
      actionsAlignment: MainAxisAlignment.end,
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
        OutlinedButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Preview")),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: AppColors.privacyTool),
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text("Send"),
        ),
      ],
    ),
  );
  return result ?? false;
}
