import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/verification_report_widget.dart';

/// Research screen — deep legal research with multi-stage progress tracking.
class ResearchScreen extends StatefulWidget {
  const ResearchScreen({super.key});

  @override
  State<ResearchScreen> createState() => _ResearchScreenState();
}

class _ResearchScreenState extends State<ResearchScreen> {
  final _queryController = TextEditingController();
  bool _isResearching = false;
  String? _currentQuery;
  List<Source> _sources = [];
  String? _researchSummary;

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  Future<void> _startResearch() async {
    final query = _queryController.text.trim();
    if (query.isEmpty) return;

    setState(() {
      _isResearching = true;
      _currentQuery = query;
      _sources = [];
      _researchSummary = null;
    });

    final appState = context.read<AppState>();
    
    // Send research query via WebSocket
    await appState.send(query, asMdx: false);
    
    // Listen for research completion via state changes
    // The actual streaming happens in the main chat flow
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
          'Legal Research',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        actions: [
          if (_isResearching)
            IconButton(
              icon: const Icon(Icons.stop),
              onPressed: () {
                // Cancel research
                setState(() {
                  _isResearching = false;
                });
              },
              tooltip: 'Stop Research',
            ),
        ],
      ),
      body: Column(
        children: [
          // Search bar
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _queryController,
                    decoration: InputDecoration(
                      hintText: 'Enter your legal research question...',
                      prefixIcon: const Icon(Icons.search),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                      filled: true,
                      fillColor: AppColors.surface,
                    ),
                    onSubmitted: (_) => _startResearch(),
                    maxLines: 3,
                    minLines: 1,
                  ),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  onPressed: _isResearching ? null : _startResearch,
                  icon: Icon(_isResearching ? Icons.hourglass_empty : Icons.auto_awesome),
                  label: Text(_isResearching ? 'Researching...' : 'Research'),
                ),
              ],
            ),
          ),

          // Progress indicator
          if (_isResearching)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: _buildProgressSection(theme, appState),
            ),

          // Results
          Expanded(
            child: _currentQuery == null
                ? _buildEmptyState(theme)
                : _isResearching && _sources.isEmpty
                    ? const Center(child: CircularProgressIndicator())
                    : ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          // Summary card
                          if (_researchSummary != null)
                            Card(
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Icon(Icons.summary, color: AppColors.accent),
                                        const SizedBox(width: 8),
                                        Text(
                                          'Research Summary',
                                          style: theme.textTheme.titleMedium?.copyWith(
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 12),
                                    Text(_researchSummary!),
                                  ],
                                ),
                              ),
                            ),
                          if (_researchSummary != null) const SizedBox(height: 16),

                          // Sources
                          Text(
                            'Sources (${_sources.length})',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 8),
                          ..._sources.map((source) => _buildSourceCard(theme, source)),
                        ],
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
          Icon(Icons.psychology, size: 64, color: AppColors.textSecondary),
          const SizedBox(height: 16),
          Text(
            'Deep Legal Research',
            style: theme.textTheme.headlineSmall?.copyWith(
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'AI-powered research with verified citations from legitimate sources',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: AppColors.textSecondary,
            ),
            textAlign: TextAlign.center,
            maxWidth: 400,
          ),
          const SizedBox(height: 24),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Example queries:',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  _buildExample('What are the elements of breach of contract in California?'),
                  _buildExample('Recent developments in GDPR enforcement actions'),
                  _buildExample('Compare qualified immunity standards across circuits'),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExample(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          const Icon(Icons.lightbulb_outline, size: 14, color: AppColors.textSecondary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgressSection(ThemeData theme, AppState appState) {
    final progress = appState.research;
    final stages = [
      {'id': ResearchStage.planning, 'label': 'Planning'},
      {'id': ResearchStage.searching, 'label': 'Searching'},
      {'id': ResearchStage.reading, 'label': 'Reading'},
      {'id': ResearchStage.writing, 'label': 'Writing'},
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 8),
            Text(
              progress.stage.isNotEmpty ? progress.stage : 'Starting research...',
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: stages.map((stage) {
            final isComplete = progress.completedStages.contains(stage['id']);
            final isCurrent = progress.stage == stage['id'];
            return Expanded(
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 12,
                    backgroundColor: isComplete
                        ? AppColors.success
                        : isCurrent
                            ? AppColors.accent
                            : AppColors.border,
                    child: Icon(
                      isComplete ? Icons.check : Icons.circle,
                      size: 12,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    stage['label'] as String,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: isComplete || isCurrent
                          ? AppColors.textPrimary
                          : AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildSourceCard(ThemeData theme, Source source) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    source.title,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: source.kind == 'document'
                        ? AppColors.accent.withOpacity(0.1)
                        : AppColors.success.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: source.kind == 'document'
                          ? AppColors.accent
                          : AppColors.success,
                    ),
                  ),
                  child: Text(
                    source.kind.toUpperCase(),
                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            if (source.snippet.isNotEmpty)
              Text(
                source.snippet,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: AppColors.textSecondary,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                if (source.page != null)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: Text(
                      'Page ${source.page}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ),
                TextButton.icon(
                  onPressed: () {
                    // Open URL
                  },
                  icon: const Icon(Icons.open_in_new, size: 14),
                  label: const Text('View'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppColors.accent,
                    padding: EdgeInsets.zero,
                    minimumSize: const Size(0, 0),
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
