import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme.dart';

/// Legal Updates screen — daily legal update monitoring with jurisdiction filtering.
class LegalUpdatesScreen extends StatefulWidget {
  const LegalUpdatesScreen({super.key});

  @override
  State<LegalUpdatesScreen> createState() => _LegalUpdatesScreenState();
}

class _LegalUpdatesScreenState extends State<LegalUpdatesScreen> {
  bool _isLoading = false;
  String _selectedJurisdiction = 'All';
  String _selectedType = 'All';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AppState>().loadLegalUpdates();
    });
  }

  Future<void> _refreshUpdates() async {
    setState(() => _isLoading = true);
    try {
      await context.read<AppState>().loadLegalUpdates();
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  List<LegalUpdate> get _filteredUpdates {
    final appState = context.read<AppState>();
    var updates = appState.legalUpdates;

    if (_selectedJurisdiction != 'All') {
      updates = updates
          .where((u) => u.jurisdiction == _selectedJurisdiction)
          .toList();
    }

    if (_selectedType != 'All') {
      updates = updates.where((u) => u.type == _selectedType).toList();
    }

    return updates;
  }

  Set<String> get _jurisdictions {
    final appState = context.read<AppState>();
    return appState.legalUpdates.map((u) => u.jurisdiction).toSet();
  }

  Set<String> get _types {
    final appState = context.read<AppState>();
    return appState.legalUpdates.map((u) => u.type).toSet();
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
          'Legal Updates',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        actions: [
          IconButton(
            icon: Icon(_isLoading ? Icons.hourglass_empty : Icons.refresh),
            onPressed: _isLoading ? null : _refreshUpdates,
            tooltip: 'Refresh Updates',
          ),
          IconButton(
            icon: const Icon(Icons.filter_list),
            onPressed: _showFilters,
            tooltip: 'Filter',
          ),
        ],
      ),
      body: Column(
        children: [
          // Filter chips
          if (_selectedJurisdiction != 'All' || _selectedType != 'All')
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  if (_selectedJurisdiction != 'All')
                    Chip(
                      label: Text(_selectedJurisdiction),
                      onDeleted: () => setState(() => _selectedJurisdiction = 'All'),
                      deleteIcon: const Icon(Icons.close, size: 18),
                    ),
                  if (_selectedType != 'All') ...[
                    const SizedBox(width: 8),
                    Chip(
                      label: Text(_selectedType),
                      onDeleted: () => setState(() => _selectedType = 'All'),
                      deleteIcon: const Icon(Icons.close, size: 18),
                    ),
                  ],
                  const Spacer(),
                  TextButton(
                    onPressed: () {
                      setState(() {
                        _selectedJurisdiction = 'All';
                        _selectedType = 'All';
                      });
                    },
                    child: const Text('Clear All'),
                  ),
                ],
              ),
            ),

          // Content
          Expanded(
            child: _isLoading && appState.legalUpdates.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : _filteredUpdates.isEmpty
                    ? _buildEmptyState(theme)
                    : ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _filteredUpdates.length,
                        itemBuilder: (context, index) {
                          final update = _filteredUpdates[index];
                          return _buildUpdateCard(theme, update);
                        },
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(ThemeData theme) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.newspaper, size: 64, color: AppColors.textSecondary),
          const SizedBox(height: 16),
          Text(
            'No Legal Updates',
            style: theme.textTheme.headlineSmall?.copyWith(
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Updates will appear here based on your jurisdiction and practice areas',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: AppColors.textSecondary,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _refreshUpdates,
            icon: const Icon(Icons.refresh),
            label: const Text('Check for Updates Now'),
          ),
        ],
      ),
    );
  }

  Widget _buildUpdateCard(ThemeData theme, LegalUpdate update) {
    final dateFmt = DateFormat('MMM d, yyyy');
    final relevanceColor = update.relevanceScore > 0.8
        ? AppColors.danger
        : update.relevanceScore > 0.5
            ? AppColors.warning
            : AppColors.success;

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    update.title,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: relevanceColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: relevanceColor),
                  ),
                  child: Text(
                    '${(update.relevanceScore * 100).toInt()}%',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: relevanceColor,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                _buildChip(update.jurisdiction, Icons.public),
                const SizedBox(width: 8),
                _buildChip(update.type, Icons.category),
                const SizedBox(width: 8),
                Text(
                  dateFmt.format(update.publishedAt),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              update.summary,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: AppColors.textPrimary,
              ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            if (update.impactSummary != null) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.accent.withOpacity(0.05),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.accent.withOpacity(0.2)),
                ),
                child: Row(
                  children: [
                    Icon(Icons.lightbulb_outline,
                        size: 18, color: AppColors.accent),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Impact: ${update.impactSummary}',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton.icon(
                  onPressed: () {
                    // Open source URL
                  },
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: const Text('View Source'),
                ),
                ElevatedButton.icon(
                  onPressed: () {
                    _showImpactSummary(update, theme);
                  },
                  icon: const Icon(Icons.summarize),
                  label: const Text('Summarize Impact'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChip(String label, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: AppColors.textSecondary),
          const SizedBox(width: 4),
          Text(
            label,
            style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  void _showFilters() {
    showModalBottomSheet(
      context: context,
      builder: (context) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Filter Updates',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 16),
            const Text('Jurisdiction'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilterChip(
                  label: const Text('All'),
                  selected: _selectedJurisdiction == 'All',
                  onSelected: (selected) {
                    setState(() => _selectedJurisdiction = 'All');
                    Navigator.pop(context);
                  },
                ),
                ..._jurisdictions.map((j) => FilterChip(
                      label: Text(j),
                      selected: _selectedJurisdiction == j,
                      onSelected: (selected) {
                        setState(() => _selectedJurisdiction = j);
                        Navigator.pop(context);
                      },
                    )),
              ],
            ),
            const SizedBox(height: 16),
            const Text('Type'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilterChip(
                  label: const Text('All'),
                  selected: _selectedType == 'All',
                  onSelected: (selected) {
                    setState(() => _selectedType = 'All');
                    Navigator.pop(context);
                  },
                ),
                ..._types.map((t) => FilterChip(
                      label: Text(t),
                      selected: _selectedType == t,
                      onSelected: (selected) {
                        setState(() => _selectedType = t);
                        Navigator.pop(context);
                      },
                    )),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _showImpactSummary(LegalUpdate update, ThemeData theme) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(update.title),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                update.summary,
                style: theme.textTheme.bodyMedium,
              ),
              if (update.impactSummary != null) ...[
                const SizedBox(height: 16),
                Text(
                  'Impact Summary',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  update.impactSummary!,
                  style: theme.textTheme.bodyMedium,
                ),
              ],
              if (update.affectedSections.isNotEmpty) ...[
                const SizedBox(height: 16),
                Text(
                  'Affected Sections',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                ...update.affectedSections.map((s) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text('• $s'),
                    )),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          ElevatedButton.icon(
            onPressed: () {
              // Generate AI summary
            },
            icon: const Icon(Icons.auto_awesome),
            label: const Text('Generate AI Brief'),
          ),
        ],
      ),
    );
  }
}
