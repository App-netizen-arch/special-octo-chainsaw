import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../services/auth_service.dart';
import '../state/app_state.dart';
import '../theme.dart';

/// Login screen — email/password authentication with role-aware redirect.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _isLoading = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final appState = context.read<AppState>();
    final result = await appState.login(
      _emailController.text.trim(),
      _passwordController.text,
    );

    if (!mounted) return;

    if (result.success) {
      // Navigate based on role
      if (result.user?.isAdmin ?? false) {
        appState.setView(MainView.admin);
      } else {
        appState.setView(MainView.chat);
      }
    } else {
      setState(() {
        _isLoading = false;
        _error = result.error ?? 'Login failed';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(32.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Logo and title
                Icon(
                  Icons.gavel,
                  size: 64,
                  color: AppColors.accent,
                ),
                const SizedBox(height: 16),
                Text(
                  'Counsel AI',
                  style: theme.textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Professional legal AI workbench',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 48),

                // Login form
                Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextFormField(
                        controller: _emailController,
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.next,
                        decoration: InputDecoration(
                          labelText: 'Email',
                          prefixIcon: const Icon(Icons.email_outlined),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          filled: true,
                          fillColor: AppColors.surface,
                        ),
                        validator: (value) {
                          if (value == null || value.isEmpty) {
                            return 'Please enter your email';
                          }
                          if (!value.contains('@')) {
                            return 'Please enter a valid email';
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _passwordController,
                        obscureText: _obscurePassword,
                        textInputAction: TextInputAction.done,
                        onFieldSubmitted: (_) => _login(),
                        decoration: InputDecoration(
                          labelText: 'Password',
                          prefixIcon: const Icon(Icons.lock_outlined),
                          suffixIcon: IconButton(
                            icon: Icon(
                              _obscurePassword
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                            ),
                            onPressed: () {
                              setState(() {
                                _obscurePassword = !_obscurePassword;
                              });
                            },
                          ),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          filled: true,
                          fillColor: AppColors.surface,
                        ),
                        validator: (value) {
                          if (value == null || value.isEmpty) {
                            return 'Please enter your password';
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 24),
                      if (_error != null)
                        Container(
                          padding: const EdgeInsets.all(12),
                          margin: const EdgeInsets.only(bottom: 16),
                          decoration: BoxDecoration(
                            color: AppColors.danger.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppColors.danger),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.error_outline,
                                  color: AppColors.danger, size: 20),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  _error!,
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    color: AppColors.danger,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ElevatedButton(
                        onPressed: _isLoading ? null : _login,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.accent,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                        child: _isLoading
                            ? const SizedBox(
                                height: 20,
                                width: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor:
                                      AlwaysStoppedAnimation<Color>(Colors.white),
                                ),
                              )
                            : const Text(
                                'Sign In',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 32),

                // Footer
                Text(
                  'By signing in, you agree to our Terms of Service and Privacy Policy.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
