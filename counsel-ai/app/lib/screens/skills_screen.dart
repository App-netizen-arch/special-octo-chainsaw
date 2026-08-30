import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme.dart';

/// Skills Manager screen — create, edit, delete, and toggle skills.
class SkillsScreen extends StatefulWidget {
  const SkillsScreen({super.key});

  @override
  State<SkillsScreen> createState() => _SkillsScreenState();
}

class _SkillsScreenState extends State<SkillsScreen> {
  bool _showBuiltIn = true;
  bool _showCustom = true;

  // Built-in skill templates
  static const _builtInSkills = [
    {
      'name': 'Legal Memo Drafting',
      'description': 'Draft legal memos with proper structure and analysis',
      'trigger': 'memo',
      'config': {'sections': ['Issue', 'Facts', 'Analysis', 'Conclusion']},
    },
    {
      'name': 'NDA Drafting',
      'description': 'Create non-disclosure agreements with standard clauses',
      'trigger': 'NDA',
      'config': {'sections': ['Confidentiality', 'Term', 'Exclusions', 'Remedies']},
    },
    {
      'name': 'Bluebook Citation',
      'description': 'Format citations according to Bluebook rules',
      'trigger': 'cite',
      'config': {'style': 'bluebook'},
    },
    {
      'name': 'Case Law Summary',
      'description': 'Summarize case law with key holdings and reasoning',
      'trigger': 'case',
      'config': {'format': 'IRAC'},
    },
    {
      'name': 'Contract Review',
      'description': 'Review contracts for common issues and risks',
      'trigger': 'review',
      'config': {'focus': ['liability', 'termination', 'indemnification']},
    },
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final appState = context.watch<AppState>();

    final allSkills = <Skill>[];
    
    // Add built-in skills
    if (_showBuiltIn) {
      for (final builtin in _builtInSkills) {
        final existing = appState.skills
            .where((s) => s.name == builtin['name'])
            .toList();
        if (existing.isNotEmpty) {
          allSkills.add(existing.first);
        } else {
          allSkills.add(Skill(
            id: 'builtin_${builtin['name']}',
            name: builtin['name'] as String,
            description: builtin['description'] as String,
            trigger: builtin['trigger'] as String,
            config: builtin['config'] as Map<String, dynamic>,
            isBuiltIn: true,
            isEnabled: true,
          ));
        }
      }
    }

    // Add custom skills
    if (_showCustom) {
      allSkills.addAll(appState.skills.where((s) => !s.isBuiltIn));
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        title: const Text(
          'Skills Manager',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => appState.loadSkills(),
            tooltip: 'Refresh',
          ),
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => _showCreateSkillDialog(context, appState),
            tooltip: 'Create Skill',
          ),
        ],
      ),
      body: Column(
        children: [
          // Filter toggles
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                FilterChip(
                  label: const Text('Built-in'),
                  selected: _showBuiltIn,
                  onSelected: (v) => setState(() => _showBuiltIn = v),
                ),
                const SizedBox(width: 8),
                FilterChip(
                  label: const Text('Custom'),
                  selected: _showCustom,
                  onSelected: (v) => setState(() => _showCustom = v),
                ),
                const Spacer(),
                Text(
                  '${allSkills.length} skills',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),

          // Skills list
          Expanded(
            child: allSkills.isEmpty
                ? _buildEmptyState(theme)
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemCount: allSkills.length,
                    itemBuilder: (context, index) {
                      final skill = allSkills[index];
                      return _buildSkillCard(theme, appState, skill);
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
          Icon(Icons.build_outlined, size: 64, color: AppColors.textSecondary),
          const SizedBox(height: 16),
          Text(
            'No Skills',
            style: theme.textTheme.headlineSmall?.copyWith(
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Create a custom skill or enable built-in skills',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: AppColors.textSecondary,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildSkillCard(ThemeData theme, AppState appState, Skill skill) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Row(
                    children: [
                      Icon(
                        skill.isBuiltIn ? Icons.star : Icons.build,
                        color: skill.isBuiltIn ? AppColors.accent : AppColors.warning,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        skill.name,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
                Switch(
                  value: skill.isEnabled,
                  onChanged: skill.isBuiltIn
                      ? null // Built-in skills can't be disabled
                      : (value) => appState.updateSkill(skill.id, {'is_enabled': value}),
                  activeColor: AppColors.success,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              skill.description,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.trigger, size: 12, color: AppColors.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        'Trigger: "${skill.trigger}"',
                        style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ),
                if (skill.isBuiltIn)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.accent.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: AppColors.accent),
                    ),
                    child: const Text(
                      'Built-in',
                      style: TextStyle(fontSize: 12, color: AppColors.accent),
                    ),
                  ),
              ],
            ),
            if (!skill.isBuiltIn) ...[
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton.icon(
                    onPressed: () => _showEditSkillDialog(context, appState, skill),
                    icon: const Icon(Icons.edit, size: 16),
                    label: const Text('Edit'),
                  ),
                  TextButton.icon(
                    onPressed: () => _confirmDelete(context, appState, skill),
                    icon: const Icon(Icons.delete, size: 16, color: AppColors.danger),
                    label: const Text(
                      'Delete',
                      style: TextStyle(color: AppColors.danger),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _showCreateSkillDialog(BuildContext context, AppState appState) {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    final triggerController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create Custom Skill'),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextFormField(
                  controller: nameController,
                  decoration: const InputDecoration(
                    labelText: 'Skill Name',
                    hintText: 'e.g., Patent Claim Drafting',
                  ),
                  validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: descController,
                  decoration: const InputDecoration(
                    labelText: 'Description',
                    hintText: 'What does this skill do?',
                  ),
                  maxLines: 3,
                  validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: triggerController,
                  decoration: const InputDecoration(
                    labelText: 'Trigger Keyword',
                    hintText: 'Word that activates this skill',
                  ),
                  validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                ),
                const SizedBox(height: 8),
                Text(
                  'This keyword in user queries will activate the skill',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              if (formKey.currentState!.validate()) {
                await appState.createSkill({
                  'name': nameController.text,
                  'description': descController.text,
                  'trigger': triggerController.text,
                  'config': {},
                  'is_enabled': true,
                });
                if (context.mounted) Navigator.pop(context);
              }
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }

  void _showEditSkillDialog(BuildContext context, AppState appState, Skill skill) {
    final nameController = TextEditingController(text: skill.name);
    final descController = TextEditingController(text: skill.description);
    final triggerController = TextEditingController(text: skill.trigger);
    final formKey = GlobalKey<FormState>();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit Skill'),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextFormField(
                  controller: nameController,
                  decoration: const InputDecoration(labelText: 'Skill Name'),
                  validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: descController,
                  decoration: const InputDecoration(labelText: 'Description'),
                  maxLines: 3,
                  validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: triggerController,
                  decoration: const InputDecoration(labelText: 'Trigger Keyword'),
                  validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              if (formKey.currentState!.validate()) {
                await appState.updateSkill(skill.id, {
                  'name': nameController.text,
                  'description': descController.text,
                  'trigger': triggerController.text,
                });
                if (context.mounted) Navigator.pop(context);
              }
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  void _confirmDelete(BuildContext context, AppState appState, Skill skill) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Skill'),
        content: Text('Are you sure you want to delete "${skill.name}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              await appState.deleteSkill(skill.id);
              if (context.mounted) Navigator.pop(context);
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.danger,
              foregroundColor: Colors.white,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}
