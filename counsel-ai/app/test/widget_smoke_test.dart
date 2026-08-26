import "package:flutter/material.dart";
import "package:flutter_test/flutter_test.dart";
import "package:counsel_ai/main.dart";
import "package:shared_preferences/shared_preferences.dart";

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  SharedPreferences.setMockInitialValues({});

  testWidgets("app boots into onboarding wizard", (tester) async {
    await tester.pumpWidget(const CounselApp());
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text("COUNSEL AI"), findsOneWidget);
    expect(find.text("Your private legal copilot."), findsOneWidget);
    expect(find.text("Skip for demo"), findsOneWidget);
  });

  testWidgets("wizard advances to jurisdiction step", (tester) async {
    await tester.pumpWidget(const CounselApp());
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, "Continue"));
    await tester.pumpAndSettle();
    expect(find.text("Where do you practise?"), findsOneWidget);
  });
}
