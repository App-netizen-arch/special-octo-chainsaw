/// Data models mirroring the backend JSON schemas.
library;

class Source {
  final String title;
  final String url;
  final String snippet;
  final String documentName;
  final int? page;
  final double relevance;
  final String kind; // web | document

  const Source({
    this.title = "Untitled source",
    this.url = "",
    this.snippet = "",
    this.documentName = "",
    this.page,
    this.relevance = 0,
    this.kind = "web",
  });

  factory Source.fromJson(Map<String, dynamic> j) => Source(
        title: (j["title"] as String?) ?? "Untitled source",
        url: (j["url"] as String?) ?? "",
        snippet: (j["snippet"] as String?) ?? "",
        documentName: (j["document_name"] as String?) ?? "",
        page: j["page"] is int ? j["page"] as int : null,
        relevance: ((j["relevance"] as num?) ?? 0).toDouble(),
        kind: (j["kind"] as String?) ?? "web",
      );

  bool get isDocument => kind == "document";

  String get citationLabel => isDocument
      ? "[${documentName.isNotEmpty ? documentName : title}${page != null ? ", Page $page" : ""}]"
      : title;
}

enum ChatMode { local, api, research, tools }

extension ChatModeX on ChatMode {
  String get wire => switch (this) {
        ChatMode.local => "local",
        ChatMode.api => "api",
        ChatMode.research => "research",
        ChatMode.tools => "tools",
      };
  String get label => switch (this) {
        ChatMode.local => "Local",
        ChatMode.api => "API",
        ChatMode.research => "Research",
        ChatMode.tools => "Tools",
      };
}

class Message {
  final String id;
  final String role; // user | assistant
  String content;
  final ChatMode mode;
  List<Source> sources;
  final DateTime createdAt;
  bool isError;
  bool streaming;

  Message({
    required this.id,
    required this.role,
    required this.content,
    required this.mode,
    this.sources = const [],
    DateTime? createdAt,
    this.isError = false,
    this.streaming = false,
  }) : createdAt = createdAt ?? DateTime.now();

  factory Message.user(String text, ChatMode mode) =>
      Message(id: _uid(), role: "user", content: text, mode: mode);

  factory Message.assistant(String text, ChatMode mode,
          {List<Source> sources = const [],
          bool streaming = false,
          bool isError = false}) =>
      Message(
          id: _uid(),
          role: "assistant",
          content: text,
          mode: mode,
          sources: sources,
          streaming: streaming,
          isError: isError);

  factory Message.fromJson(Map<String, dynamic> j) => Message(
        id: (j["id"] as String?) ?? _uid(),
        role: (j["role"] as String?) ?? "assistant",
        content: (j["content"] as String?) ?? "",
        mode: ChatMode.values.firstWhere((m) => m.wire == j["mode"],
            orElse: () => ChatMode.api),
        sources: ((j["sources"] as List?) ?? [])
            .whereType<Map<String, dynamic>>()
            .map(Source.fromJson)
            .toList(),
        createdAt: DateTime.tryParse("${j["created_at"] ?? ""}") ?? DateTime.now(),
      );

  static String _uid() =>
      DateTime.now().microsecondsSinceEpoch.toRadixString(36);
}

class Conversation {
  final String id;
  final String title;
  final int updatedAtMs;

  Conversation({required this.id, required this.title, this.updatedAtMs = 0});

  factory Conversation.fromJson(Map<String, dynamic> j) => Conversation(
        id: j["id"] as String,
        title: (j["title"] as String?) ?? "Untitled",
        updatedAtMs: ((j["updated_at"] as num?) ?? 0).toInt(),
      );
}

class LegalDocument {
  final String id;
  final String name;
  final int pages;
  final int chunks;

  LegalDocument({required this.id, required this.name, this.pages = 0, this.chunks = 0});

  factory LegalDocument.fromJson(Map<String, dynamic> j) => LegalDocument(
        id: j["id"] as String,
        name: (j["name"] as String?) ?? "document",
        pages: (j["pages"] as num?)?.toInt() ?? 0,
        chunks: (j["chunks"] as num?)?.toInt() ?? 0,
      );
}

class ToolDef {
  final String slug;
  final String name;
  final String description;
  final bool requiresExternalSend;

  ToolDef({required this.slug, required this.name, required this.description, this.requiresExternalSend = true});

  factory ToolDef.fromJson(Map<String, dynamic> j) => ToolDef(
        slug: j["slug"] as String,
        name: (j["name"] as String?) ?? j["slug"],
        description: (j["description"] as String?) ?? "",
        requiresExternalSend: (j["requires_external_send"] as bool?) ?? true,
      );
}

class ResearchStage {
  static const planning = "planning";
  static const searching = "searching";
  static const reading = "reading";
  static const writing = "writing";
  static const done = "done";
}

// ============================================================
// New production models (auth, skills, legal updates, verification, audit)
// ============================================================

class User {
  final String id;
  final String email;
  final String? fullName;
  final String role; // admin | lawyer | paralegal | viewer
  final String? firmId;
  final DateTime createdAt;
  final bool isActive;

  const User({
    required this.id,
    required this.email,
    this.fullName,
    required this.role,
    this.firmId,
    required this.createdAt,
    this.isActive = true,
  });

  factory User.fromJson(Map<String, dynamic> j) => User(
        id: j["id"] as String,
        email: (j["email"] as String?) ?? "",
        fullName: j["full_name"] as String?,
        role: (j["role"] as String?) ?? "viewer",
        firmId: j["firm_id"] as String?,
        createdAt: DateTime.tryParse(j["created_at"] as String? ?? "") ?? DateTime.now(),
        isActive: (j["is_active"] as bool?) ?? true,
      );

  bool get isAdmin => role == "admin";
  bool get isLawyer => role == "lawyer" || isAdmin;
}

class Skill {
  final String id;
  final String name;
  final String description;
  final String trigger; // keyword/phrase that activates this skill
  final Map<String, dynamic> config;
  final bool isEnabled;
  final bool isBuiltIn;
  final DateTime? updatedAt;

  const Skill({
    required this.id,
    required this.name,
    required this.description,
    required this.trigger,
    required this.config,
    this.isEnabled = true,
    this.isBuiltIn = false,
    this.updatedAt,
  });

  factory Skill.fromJson(Map<String, dynamic> j) => Skill(
        id: j["id"] as String,
        name: (j["name"] as String?) ?? "Unnamed Skill",
        description: (j["description"] as String?) ?? "",
        trigger: (j["trigger"] as String?) ?? "",
        config: (j["config"] as Map<String, dynamic>?) ?? {},
        isEnabled: (j["is_enabled"] as bool?) ?? true,
        isBuiltIn: (j["is_builtin"] as bool?) ?? false,
        updatedAt: DateTime.tryParse(j["updated_at"] as String? ?? ""),
      );
}

class LegalUpdate {
  final String id;
  final String title;
  final String summary;
  final String jurisdiction;
  final String type; // regulation | case | statute | guidance
  final String sourceUrl;
  final DateTime publishedAt;
  final double relevanceScore;
  final String? impactSummary;
  final List<String> affectedSections;

  const LegalUpdate({
    required this.id,
    required this.title,
    required this.summary,
    required this.jurisdiction,
    required this.type,
    required this.sourceUrl,
    required this.publishedAt,
    this.relevanceScore = 0.0,
    this.impactSummary,
    this.affectedSections = const [],
  });

  factory LegalUpdate.fromJson(Map<String, dynamic> j) => LegalUpdate(
        id: j["id"] as String,
        title: (j["title"] as String?) ?? "Untitled Update",
        summary: (j["summary"] as String?) ?? "",
        jurisdiction: (j["jurisdiction"] as String?) ?? "Unknown",
        type: (j["type"] as String?) ?? "guidance",
        sourceUrl: (j["source_url"] as String?) ?? "",
        publishedAt: DateTime.tryParse(j["published_at"] as String? ?? "") ?? DateTime.now(),
        relevanceScore: ((j["relevance_score"] as num?) ?? 0.0).toDouble(),
        impactSummary: j["impact_summary"] as String?,
        affectedSections: ((j["affected_sections"] as List?) ?? [])
            .whereType<String>()
            .toList(),
      );
}

class VerificationReport {
  final bool passed;
  final List<CitationIssue> citationIssues;
  final List<SourceIssue> sourceIssues;
  final List<ClauseIssue> clauseIssues;
  final List<PiiFinding> piiFindings;
  final JurisdictionCheck? jurisdictionCheck;
  final String? overallSummary;

  const VerificationReport({
    this.passed = false,
    this.citationIssues = const [],
    this.sourceIssues = const [],
    this.clauseIssues = const [],
    this.piiFindings = const [],
    this.jurisdictionCheck,
    this.overallSummary,
  });

  factory VerificationReport.fromJson(Map<String, dynamic> j) => VerificationReport(
        passed: (j["passed"] as bool?) ?? false,
        citationIssues: ((j["citation_issues"] as List?) ?? [])
            .whereType<Map<String, dynamic>>()
            .map(CitationIssue.fromJson)
            .toList(),
        sourceIssues: ((j["source_issues"] as List?) ?? [])
            .whereType<Map<String, dynamic>>()
            .map(SourceIssue.fromJson)
            .toList(),
        clauseIssues: ((j["clause_issues"] as List?) ?? [])
            .whereType<Map<String, dynamic>>()
            .map(ClauseIssue.fromJson)
            .toList(),
        piiFindings: ((j["pii_findings"] as List?) ?? [])
            .whereType<Map<String, dynamic>>()
            .map(PiiFinding.fromJson)
            .toList(),
        jurisdictionCheck: j["jurisdiction_check"] != null
            ? JurisdictionCheck.fromJson(j["jurisdiction_check"] as Map<String, dynamic>)
            : null,
        overallSummary: j["overall_summary"] as String?,
      );

  int get totalIssues =>
      citationIssues.length + sourceIssues.length + clauseIssues.length + piiFindings.length;
}

class CitationIssue {
  final String citation;
  final String style; // bluebook | oscola | unknown
  final bool isValid;
  final String? message;

  const CitationIssue({
    required this.citation,
    required this.style,
    this.isValid = false,
    this.message,
  });

  factory CitationIssue.fromJson(Map<String, dynamic> j) => CitationIssue(
        citation: (j["citation"] as String?) ?? "",
        style: (j["style"] as String?) ?? "unknown",
        isValid: (j["is_valid"] as bool?) ?? false,
        message: j["message"] as String?,
      );
}

class SourceIssue {
  final String url;
  final bool exists;
  final int? statusCode;
  final String? quoteMatch;
  final String? message;

  const SourceIssue({
    required this.url,
    this.exists = false,
    this.statusCode,
    this.quoteMatch,
    this.message,
  });

  factory SourceIssue.fromJson(Map<String, dynamic> j) => SourceIssue(
        url: (j["url"] as String?) ?? "",
        exists: (j["exists"] as bool?) ?? false,
        statusCode: j["status_code"] as int?,
        quoteMatch: j["quote_match"] as String?,
        message: j["message"] as String?,
      );
}

class ClauseIssue {
  final String clauseType;
  final bool isPresent;
  final String? message;

  const ClauseIssue({
    required this.clauseType,
    this.isPresent = false,
    this.message,
  });

  factory ClauseIssue.fromJson(Map<String, dynamic> j) => ClauseIssue(
        clauseType: (j["clause_type"] as String?) ?? "",
        isPresent: (j["is_present"] as bool?) ?? false,
        message: j["message"] as String?,
      );
}

class PiiFinding {
  final String type; // email | phone | ssn | credit_card | address
  final String value;
  final int start;
  final int end;
  final bool isRedacted;

  const PiiFinding({
    required this.type,
    required this.value,
    required this.start,
    required this.end,
    this.isRedacted = false,
  });

  factory PiiFinding.fromJson(Map<String, dynamic> j) => PiiFinding(
        type: (j["type"] as String?) ?? "unknown",
        value: (j["value"] as String?) ?? "",
        start: (j["start"] as int?) ?? 0,
        end: (j["end"] as int?) ?? 0,
        isRedacted: (j["is_redacted"] as bool?) ?? false,
      );
}

class JurisdictionCheck {
  final String governingLaw;
  final bool isPresent;
  final List<String> conflicts;

  const JurisdictionCheck({
    required this.governingLaw,
    this.isPresent = false,
    this.conflicts = const [],
  });

  factory JurisdictionCheck.fromJson(Map<String, dynamic> j) => JurisdictionCheck(
        governingLaw: (j["governing_law"] as String?) ?? "",
        isPresent: (j["is_present"] as bool?) ?? false,
        conflicts: ((j["conflicts"] as List?) ?? []).whereType<String>().toList(),
      );
}

class ToolConnection {
  final String id;
  final String provider; // gmail | outlook | calendar
  final String? userEmail;
  final bool isConnected;
  final DateTime? connectedAt;
  final DateTime? expiresAt;
  final List<String> scopes;

  const ToolConnection({
    required this.id,
    required this.provider,
    this.userEmail,
    this.isConnected = false,
    this.connectedAt,
    this.expiresAt,
    this.scopes = const [],
  });

  factory ToolConnection.fromJson(Map<String, dynamic> j) => ToolConnection(
        id: j["id"] as String,
        provider: (j["provider"] as String?) ?? "unknown",
        userEmail: j["user_email"] as String?,
        isConnected: (j["is_connected"] as bool?) ?? false,
        connectedAt: DateTime.tryParse(j["connected_at"] as String? ?? ""),
        expiresAt: DateTime.tryParse(j["expires_at"] as String? ?? ""),
        scopes: ((j["scopes"] as List?) ?? []).whereType<String>().toList(),
      );
}

class AuditEntry {
  final String id;
  final String userId;
  final String action;
  final String resourceType;
  final String? resourceId;
  final Map<String, dynamic>? details;
  final DateTime timestamp;
  final String? ipAddress;

  const AuditEntry({
    required this.id,
    required this.userId,
    required this.action,
    required this.resourceType,
    this.resourceId,
    this.details,
    required this.timestamp,
    this.ipAddress,
  });

  factory AuditEntry.fromJson(Map<String, dynamic> j) => AuditEntry(
        id: j["id"] as String,
        userId: (j["user_id"] as String?) ?? "",
        action: (j["action"] as String?) ?? "",
        resourceType: (j["resource_type"] as String?) ?? "",
        resourceId: j["resource_id"] as String?,
        details: j["details"] as Map<String, dynamic>?,
        timestamp: DateTime.tryParse(j["timestamp"] as String? ?? "") ?? DateTime.now(),
        ipAddress: j["ip_address"] as String?,
      );
}
