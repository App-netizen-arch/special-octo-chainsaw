/// Authentication service — JWT token management, login/logout, refresh flow.
library;

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/models.dart';

const _storage = FlutterSecureStorage();
const _prefsKey = 'counsel_auth_prefs';

class AuthTokens {
  final String accessToken;
  final String refreshToken;
  final DateTime expiresAt;

  const AuthTokens({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
  });

  bool get isExpired => DateTime.now().isAfter(expiresAt.subtract(const Duration(minutes: 2)));

  factory AuthTokens.fromJson(Map<String, dynamic> j) {
    final now = DateTime.now();
    // Backend returns expires_in (seconds) or exp (timestamp)
    final expiresIn = j['expires_in'] as int? ?? 1800; // default 30min
    return AuthTokens(
      accessToken: j['access_token'] as String,
      refreshToken: j['refresh_token'] as String,
      expiresAt: now.add(Duration(seconds: expiresIn)),
    );
  }
}

class AuthService {
  AuthService({required this.baseUrl});

  final String baseUrl;

  User? _currentUser;
  AuthTokens? _tokens;
  bool _isInitialized = false;

  User? get currentUser => _currentUser;
  bool get isAuthenticated => _tokens != null && !_tokens!.isExpired;
  bool get isInitialized => _isInitialized;

  /// Initialize auth state from secure storage
  Future<void> init() async {
    if (_isInitialized) return;

    try {
      final storedTokens = await _storage.read(key: 'auth_tokens');
      final storedUser = await _storage.read(key: 'current_user');

      if (storedTokens != null) {
        final tokenData = jsonDecode(storedTokens) as Map<String, dynamic>;
        _tokens = AuthTokens.fromJson(tokenData);
      }

      if (storedUser != null) {
        final userData = jsonDecode(storedUser) as Map<String, dynamic>;
        _currentUser = User.fromJson(userData);
      }

      // If tokens exist but are expired, try to refresh
      if (_tokens != null && _tokens!.isExpired) {
        await _refreshTokens();
      }
    } catch (_) {
      // Storage unavailable or corrupted, clear state
      await logout();
    }

    _isInitialized = true;
  }

  /// Login with email/password
  Future<LoginResult> login(String email, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email, 'password': password}),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _tokens = AuthTokens.fromJson(data);
        
        // Extract user info from token or separate endpoint
        if (data['user'] != null) {
          _currentUser = User.fromJson(data['user'] as Map<String, dynamic>);
        } else {
          // Fetch current user
          await _fetchCurrentUser();
        }

        await _persistTokens();
        await _persistUser();

        return LoginResult(success: true, user: _currentUser);
      } else if (response.statusCode == 401) {
        return LoginResult(success: false, error: 'Invalid email or password');
      } else {
        final error = _extractError(response);
        return LoginResult(success: false, error: error);
      }
    } catch (e) {
      return LoginResult(success: false, error: 'Network error: ${e.toString()}');
    }
  }

  /// Logout and clear all stored credentials
  Future<void> logout() async {
    _tokens = null;
    _currentUser = null;
    await _storage.delete(key: 'auth_tokens');
    await _storage.delete(key: 'current_user');
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('$_prefsKey.base_url');
  }

  /// Get valid access token, refreshing if necessary
  Future<String?> getToken() async {
    if (_tokens == null) return null;

    if (_tokens!.isExpired) {
      final refreshed = await _refreshTokens();
      if (!refreshed) return null;
    }

    return _tokens!.accessToken;
  }

  /// Refresh access token using refresh token
  Future<bool> _refreshTokens() async {
    if (_tokens == null || _tokens!.refreshToken.isEmpty) {
      return false;
    }

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/auth/refresh'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': _tokens!.refreshToken}),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _tokens = AuthTokens.fromJson(data);
        await _persistTokens();
        return true;
      } else {
        // Refresh failed, require re-login
        await logout();
        return false;
      }
    } catch (_) {
      return false;
    }
  }

  /// Fetch current user profile
  Future<User?> _fetchCurrentUser() async {
    final token = _tokens?.accessToken;
    if (token == null) return null;

    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/auth/me'),
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _currentUser = User.fromJson(data);
        await _persistUser();
        return _currentUser;
      }
    } catch (_) {}

    return null;
  }

  Future<void> _persistTokens() async {
    if (_tokens != null) {
      await _storage.write(
        key: 'auth_tokens',
        value: jsonEncode({
          'access_token': _tokens!.accessToken,
          'refresh_token': _tokens!.refreshToken,
          'expires_in': _tokens!.expiresAt.difference(DateTime.now()).inSeconds,
        }),
      );
    }
  }

  Future<void> _persistUser() async {
    if (_currentUser != null) {
      await _storage.write(
        key: 'current_user',
        value: jsonEncode({
          'id': _currentUser!.id,
          'email': _currentUser!.email,
          'full_name': _currentUser!.fullName,
          'role': _currentUser!.role,
          'firm_id': _currentUser!.firmId,
          'created_at': _currentUser!.createdAt.toIso8601String(),
          'is_active': _currentUser!.isActive,
        }),
      );
    }
  }

  static String _extractError(http.Response response) {
    try {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return data['detail'] as String? ?? 'Request failed (${response.statusCode})';
    } catch (_) {
      return 'Request failed (${response.statusCode})';
    }
  }
}

class LoginResult {
  final bool success;
  final User? user;
  final String? error;

  LoginResult({required this.success, this.user, this.error});
}
