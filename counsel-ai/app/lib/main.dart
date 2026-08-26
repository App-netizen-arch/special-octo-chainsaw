import "package:flutter/material.dart";
import "package:provider/provider.dart";

import "screens/home_screen.dart";
import "screens/onboarding_screen.dart";
import "state/app_state.dart";
import "theme.dart";

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const CounselApp());
}

class CounselApp extends StatelessWidget {
  const CounselApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AppState()..init(),
      child: Consumer<AppState>(
        builder: (context, state, _) => MaterialApp(
          title: "Counsel AI",
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light(),
          home: AnimatedSwitcher(
            duration: const Duration(milliseconds: 250),
            child: !state.onboarded ? const OnboardingScreen(key: ValueKey("onboarding")) : const HomeScreen(key: ValueKey("home")),
          ),
        ),
      ),
    );
  }
}
