/// Design system — strict color + typography tokens from the spec.
library;

import "package:flutter/material.dart";

class AppColors {
  static const background = Color(0xFFFFFFFF);
  static const surface = Color(0xFFF7F7F8);
  static const textPrimary = Color(0xFF1A1A1A);
  static const textSecondary = Color(0xFF6B7280);
  static const border = Color(0xFFE5E7EB);
  static const accent = Color(0xFF1B4965);
  static const success = Color(0xFF15803D);
  static const warning = Color(0xFFB45309);
  static const danger = Color(0xFFB91C1C);
  // privacy colors
  static const privacyLocal = Color(0xFF047857);
  static const privacyApi = Color(0xFFD97706);
  static const privacyTool = Color(0xFFB91C1C);
}

class AppTheme {
  /// UI font: prefer bundled Inter, fall back to platform sans.
  static const uiFont = "Inter";
  /// Document font for MDX preview (serif legal look).
  static const docFont = "SourceSerifPro";
  static const docFontFallback = ["Georgia", "Times New Roman", "serif"];

  static ThemeData light() {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppColors.background,
      fontFamily: uiFont,
    );
    const radius = BorderRadius.all(Radius.circular(10));
    return base.copyWith(
      colorScheme: base.colorScheme.copyWith(
        primary: AppColors.accent,
        secondary: AppColors.accent,
        surface: AppColors.background,
        error: AppColors.danger,
        outline: AppColors.border,
      ),
      textTheme: _textTheme(base.textTheme),
      dividerColor: AppColors.border,
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface,
        border: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: AppColors.border)),
        enabledBorder: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: AppColors.border)),
        focusedBorder: OutlineInputBorder(
          borderRadius: radius,
          borderSide: BorderSide(color: AppColors.accent, width: 1.4),
        ),
        hintStyle: const TextStyle(color: AppColors.textSecondary, fontSize: 14),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
      tooltipTheme: const TooltipThemeData(
        decoration: BoxDecoration(color: AppColors.accent, borderRadius: BorderRadius.all(Radius.circular(6))),
        textStyle: TextStyle(color: Colors.white, fontSize: 12),
      ),
    );
  }

  static TextTheme _textTheme(TextTheme fallback) {
    final base = fallback.apply(bodyColor: AppColors.textPrimary, displayColor: AppColors.textPrimary);
    return base.copyWith(
      headlineMedium: base.headlineMedium?.copyWith(fontSize: 28, fontWeight: FontWeight.w600),
      titleLarge: base.titleLarge?.copyWith(fontSize: 20, fontWeight: FontWeight.w600),
      titleMedium: base.titleMedium?.copyWith(fontSize: 16, fontWeight: FontWeight.w600),
      bodyMedium: base.bodyMedium?.copyWith(fontSize: 14, height: 1.6),
      bodySmall: base.bodySmall?.copyWith(fontSize: 12.5, height: 1.5),
      labelSmall: base.labelSmall?.copyWith(fontSize: 11, letterSpacing: 0.8, color: AppColors.textSecondary),
    );
  }

  /// Serif style used by the MDX document preview.
  static TextStyle document({double? size, FontWeight? weight}) => TextStyle(
        fontFamily: docFont,
        fontFamilyFallback: docFontFallback,
        fontSize: size ?? 15,
        height: 1.65,
        fontWeight: weight ?? FontWeight.w400,
        color: AppColors.textPrimary,
      );

  static TextStyle mono() => const TextStyle(
        fontFamily: "monospace",
        fontSize: 12,
        height: 1.5,
        color: AppColors.textSecondary,
      );
}
