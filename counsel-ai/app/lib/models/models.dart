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
