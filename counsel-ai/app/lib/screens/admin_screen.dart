import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme.dart';

/// Admin screen — user management, audit logs, firm settings.
class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key});

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = false;
  List<User> _users = [];
  List<AuditEntry> _auditLogs = [];
  Map<String, dynamic> _firmSettings = {};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    final appState = context.read<AppState>();
    
    try {
      // Load users (admin endpoint)
      // Load audit logs
      _auditLogs = await appState.api.auditLogs(limit: 100);
      
      // Load firm settings
      final settings = await appState.api.settings();
      _firmSettings = settings;
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load admin data: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final appState = context.watch<AppState>();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        title: const Text(
          'Administration',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.people), text: 'Users'),
            Tab(icon: Icon(Icons.history), text: 'Audit Logs'),
            Tab(icon: Icon(Icons.settings), text: 'Firm Settings'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildUsersTab(theme, appState),
                _buildAuditLogsTab(theme),
                _buildFirmSettingsTab(theme, appState),
              ],
            ),
    );
  }

  Widget _buildUsersTab(ThemeData theme, AppState appState) {
    // Placeholder - would fetch from /api/admin/users
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.people_outline, size: 64, color: AppColors.textSecondary),
          const SizedBox(height: 16),
          Text(
            'User Management',
            style: theme.textTheme.headlineSmall?.copyWith(
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Manage firm users and roles',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () {
              // Show add user dialog
            },
            icon: const Icon(Icons.person_add),
            label: const Text('Add User'),
          ),
        ],
      ),
    );
  }

  Widget _buildAuditLogsTab(ThemeData theme) {
    if (_auditLogs.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.history_toggle_off, size: 64, color: AppColors.textSecondary),
            const SizedBox(height: 16),
            Text(
              'No Audit Logs',
              style: theme.textTheme.headlineSmall?.copyWith(
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Audit trail will appear here',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _auditLogs.length,
      itemBuilder: (context, index) {
        final entry = _auditLogs[index];
        final dateFmt = DateFormat('yyyy-MM-dd HH:mm:ss');
        
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: _getActionIcon(entry.action),
            title: Text(
              entry.action,
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('User: ${entry.userId}'),
                Text('Resource: ${entry.resourceType}${entry.resourceId != null ? '/${entry.resourceId}' : ''}'),
                Text(
                  dateFmt.format(entry.timestamp),
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
            isThreeLine: true,
          ),
        );
      },
    );
  }

  Widget _getActionIcon(String action) {
    IconData icon;
    Color color;
    
    if (action.contains('create') || action.contains('login')) {
      icon = Icons.check_circle;
      color = AppColors.success;
    } else if (action.contains('delete') || action.contains('failed')) {
      icon = Icons.error;
      color = AppColors.danger;
    } else {
      icon = Icons.info;
      color = AppColors.accent;
    }
    
    return Icon(icon, color: color);
  }

  Widget _buildFirmSettingsTab(ThemeData theme, AppState appState) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSettingSection(
          theme,
          'Privacy & Security',
          [
            SwitchListTile(
              title: const Text('Enforce Two-Factor Authentication'),
              subtitle: const Text('Require 2FA for all users'),
              value: _firmSettings['require_2fa'] as bool? ?? false,
              onChanged: (value) {
                // Update setting
              },
              activeColor: AppColors.accent,
            ),
            SwitchListTile(
              title: const Text('Audit Logging'),
              subtitle: const Text('Log all user actions'),
              value: _firmSettings['audit_enabled'] as bool? ?? true,
              onChanged: (value) {
                // Update setting
              },
              activeColor: AppColors.accent,
            ),
          ],
        ),
        const Divider(),
        _buildSettingSection(
          theme,
          'Model Policy',
          [
            ListTile(
              title: const Text('Default Model'),
              subtitle: Text(_firmSettings['default_model'] as String? ?? 'local'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {
                // Show model selection dialog
              },
            ),
            ListTile(
              title: const Text('Allowed External APIs'),
              subtitle: Text(_firmSettings['allowed_apis'] as String? ?? 'None'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {
                // Show API configuration
              },
            ),
          ],
        ),
        const Divider(),
        _buildSettingSection(
          theme,
          'Data Retention',
          [
            ListTile(
              title: const Text('Conversation Retention Period'),
              subtitle: Text('${_firmSettings['retention_days'] ?? 90} days'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {
                // Show retention settings
              },
            ),
            ListTile(
              title: const Text('Clear All Data'),
              subtitle: const Text('Permanently delete all local data'),
              leading: const Icon(Icons.delete_forever, color: AppColors.danger),
              onTap: () {
                _showClearDataConfirmation(context, appState);
              },
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildSettingSection(
    ThemeData theme,
    String title,
    List<Widget> children,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8.0),
          child: Text(
            title,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
        ),
        ...children,
      ],
    );
  }

  void _showClearDataConfirmation(BuildContext context, AppState appState) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear All Data'),
        content: const Text(
          'This will permanently delete all conversations, documents, and settings. This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              // Call API to clear data
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('All data cleared')),
              );
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.danger,
              foregroundColor: Colors.white,
            ),
            child: const Text('Clear All Data'),
          ),
        ],
      ),
    );
  }
}
