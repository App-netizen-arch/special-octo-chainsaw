import 'package:flutter/material.dart';
import '../models/models.dart';
import '../theme.dart';

/// Verification Report Widget — displays multi-agent verification results.
class VerificationReportWidget extends StatelessWidget {
  const VerificationReportWidget({
    super.key,
    required this.report,
    this.onRetry,
  });

  final VerificationReport report;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.all(16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                Icon(
                  report.passed ? Icons.check_circle : Icons.warning,
                  color: report.passed ? AppColors.success : AppColors.warning,
                  size: 28,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Verification Report',
                        style: theme.textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        report.overallSummary ?? _generateSummary(),
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                if (onRetry != null)
                  ElevatedButton.icon(
                    onPressed: onRetry,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Re-verify'),
                  ),
              ],
            ),
            const Divider(height: 32),

            // Issues summary
            if (!report.passed) ...[
              Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  if (report.citationIssues.isNotEmpty)
                    _buildIssueCount(
                      theme,
                      Icons.format_quote,
                      'Citation Issues',
                      report.citationIssues.length,
                      AppColors.warning,
                    ),
                  if (report.sourceIssues.isNotEmpty)
                    _buildIssueCount(
                      theme,
                      Icons.link,
                      'Source Issues',
                      report.sourceIssues.length,
                      AppColors.danger,
                    ),
                  if (report.clauseIssues.isNotEmpty)
                    _buildIssueCount(
                      theme,
                      Icons.description,
                      'Clause Issues',
                      report.clauseIssues.length,
                      AppColors.warning,
                    ),
                  if (report.piiFindings.isNotEmpty)
                    _buildIssueCount(
                      theme,
                      Icons.security,
                      'PII Findings',
                      report.piiFindings.length,
                      AppColors.danger,
                    ),
                ],
              ),
              const Divider(height: 32),
            ],

            // Detailed sections
            if (report.citationIssues.isNotEmpty) ...[
              _buildSection(
                theme,
                'Citation Validation',
                report.citationIssues.map((i) => _buildCitationIssue(theme, i)).toList(),
              ),
            ],
            if (report.sourceIssues.isNotEmpty) ...[
              const SizedBox(height: 16),
              _buildSection(
                theme,
                'Source Existence',
                report.sourceIssues.map((i) => _buildSourceIssue(theme, i)).toList(),
              ),
            ],
            if (report.clauseIssues.isNotEmpty) ...[
              const SizedBox(height: 16),
              _buildSection(
                theme,
                'Clause Structure',
                report.clauseIssues.map((i) => _buildClauseIssue(theme, i)).toList(),
              ),
            ],
            if (report.piiFindings.isNotEmpty) ...[
              const SizedBox(height: 16),
              _buildSection(
                theme,
                'PII Detection',
                report.piiFindings.map((i) => _buildPiiFinding(theme, i)).toList(),
              ),
            ],
            if (report.jurisdictionCheck != null) ...[
              const SizedBox(height: 16),
              _buildSection(
                theme,
                'Jurisdiction Check',
                [_buildJurisdictionCheck(theme, report.jurisdictionCheck!)],
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _generateSummary() {
    final total = report.totalIssues;
    if (total == 0) return 'All checks passed successfully';
    if (total == 1) return '1 issue found';
    return '$total issues found';
  }

  Widget _buildIssueCount(
    ThemeData theme,
    IconData icon,
    String label,
    int count,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '$count',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: color,
                ),
              ),
              Text(
                label,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSection(
    ThemeData theme,
    String title,
    List<Widget> children,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 12),
        ...children,
      ],
    );
  }

  Widget _buildCitationIssue(ThemeData theme, CitationIssue issue) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: issue.isValid
            ? AppColors.success.withOpacity(0.05)
            : AppColors.warning.withOpacity(0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: issue.isValid ? AppColors.success : AppColors.warning,
        ),
      ),
      child: Row(
        children: [
          Icon(
            issue.isValid ? Icons.check_circle : Icons.warning,
            color: issue.isValid ? AppColors.success : AppColors.warning,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  issue.citation,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
                if (issue.message != null)
                  Text(
                    issue.message!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                Text(
                  'Style: ${issue.style.toUpperCase()}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSourceIssue(ThemeData theme, SourceIssue issue) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: issue.exists
            ? AppColors.success.withOpacity(0.05)
            : AppColors.danger.withOpacity(0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: issue.exists ? AppColors.success : AppColors.danger,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                issue.exists ? Icons.check_circle : Icons.error,
                color: issue.exists ? AppColors.success : AppColors.danger,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                issue.exists ? 'Source Verified' : 'Source Not Found',
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: issue.exists ? AppColors.success : AppColors.danger,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            issue.url,
            style: theme.textTheme.bodySmall?.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          if (issue.statusCode != null) ...[
            const SizedBox(height: 4),
            Text(
              'Status: ${issue.statusCode}',
              style: theme.textTheme.bodySmall,
            ),
          ],
          if (issue.quoteMatch != null) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                '"${issue.quoteMatch}"',
                style: theme.textTheme.bodySmall?.copyWith(
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
          ],
          if (issue.message != null) ...[
            const SizedBox(height: 4),
            Text(
              issue.message!,
              style: theme.textTheme.bodySmall?.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildClauseIssue(ThemeData theme, ClauseIssue issue) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: issue.isPresent
            ? AppColors.success.withOpacity(0.05)
            : AppColors.warning.withOpacity(0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: issue.isPresent ? AppColors.success : AppColors.warning,
        ),
      ),
      child: Row(
        children: [
          Icon(
            issue.isPresent ? Icons.check_circle : Icons.warning,
            color: issue.isPresent ? AppColors.success : AppColors.warning,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${issue.clauseType} Clause',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Text(
                  issue.isPresent ? 'Present' : 'Missing',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: issue.isPresent ? AppColors.success : AppColors.warning,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (issue.message != null)
                  Text(
                    issue.message!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPiiFinding(ThemeData theme, PiiFinding finding) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.danger.withOpacity(0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.danger),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.security,
            color: AppColors.danger,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${_piiTypeLabel(finding.type)} Detected',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: AppColors.danger,
                  ),
                ),
                Text(
                  finding.isRedacted ? 'Redacted' : 'Requires Review',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: finding.isRedacted ? AppColors.success : AppColors.danger,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _piiTypeLabel(String type) {
    switch (type) {
      case 'email':
        return 'Email Address';
      case 'phone':
        return 'Phone Number';
      case 'ssn':
        return 'Social Security Number';
      case 'credit_card':
        return 'Credit Card Number';
      case 'address':
        return 'Physical Address';
      default:
        return 'PII';
    }
  }

  Widget _buildJurisdictionCheck(
    ThemeData theme,
    JurisdictionCheck check,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: check.isPresent && check.conflicts.isEmpty
            ? AppColors.success.withOpacity(0.05)
            : AppColors.warning.withOpacity(0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: check.isPresent && check.conflicts.isEmpty
              ? AppColors.success
              : AppColors.warning,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                check.isPresent && check.conflicts.isEmpty
                    ? Icons.check_circle
                    : Icons.warning,
                color: check.isPresent && check.conflicts.isEmpty
                    ? AppColors.success
                    : AppColors.warning,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Governing Law: ${check.governingLaw}',
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          if (check.conflicts.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Conflicts detected:',
              style: theme.textTheme.bodySmall?.copyWith(
                color: AppColors.warning,
                fontWeight: FontWeight.w600,
              ),
            ),
            ...check.conflicts.map((c) => Padding(
                  padding: const EdgeInsets.only(left: 20, top: 4),
                  child: Text(
                    '• $c',
                    style: theme.textTheme.bodySmall,
                  ),
                )),
          ],
        ],
      ),
    );
  }
}
