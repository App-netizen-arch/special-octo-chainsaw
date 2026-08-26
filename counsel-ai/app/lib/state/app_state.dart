/// Global application state (provider + ChangeNotifier).
library;

import "dart:async";
import "dart:convert";

import "package:flutter/foundation.dart";
import "package:flutter_secure_storage/flutter_secure_storage.dart";
import "package:shared_preferences/shared_preferences.dart";

import "../models/models.dart";
import "../services/api_client.dart";
import "../services/websocket_client.dart";

enum MainView { chat, document, settings }

enum ConnectionStatus { unknown, connected, offline }

class ResearchProgress {
  String stage = "";
  String detail = "";
  final Set<String> completedStages = {};
}

class AppState extends ChangeNotifier {
  // -------------------------------------------------------------- config --
  static const defaultBaseUrl = "http://127.0.0.1:8000";
  static const defaultToken = "counsel-dev-token";

  String baseUrl = defaultBaseUrl;
  String get wsBase => baseUrl.replaceFirst(RegExp(r"^http"), "ws");
  String apiToken = defaultToken;
  String apiKey = ""; // lives ONLY in the OS keychain until sent per-turn

  ApiClient? _api;
  ApiClient get api {
    _api ??= ApiClient(baseUrl: baseUrl, token: apiToken);
    return _api!;
  }

  void reconnectClient() => _api = ApiClient(baseUrl: baseUrl, token: apiToken);

  // ---------------------------------------------------------------- state --
  ConnectionStatus backendStatus = ConnectionStatus.unknown;
  bool onboarded = false;
  MainView view = MainView.chat;
  ChatMode mode = ChatMode.local;

  List<Conversation> conversations = [];
  String? activeConversationId;
  List<Message> messages = [];

  bool isStreaming = false;
  final StringBuffer streamBuffer = StringBuffer();
  List<Source> pendingSources = [];
  ResearchProgress research = ResearchProgress();

  List<LegalDocument> documents = [];
  final Set<String> attachedDocIds = {};

  List<ToolDef> tools = [];
  String lastToolResult = "";

  // document editor state
  String mdxText = "";
  double docSplitRatio = 0.45;
  String activeTemplateLabel = "";

  Map<String, dynamic> jurisdictionData = {"countries": <String>[], "provinces": <String, dynamic>{}};

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    baseUrl = prefs.getString("baseUrl") ?? defaultBaseUrl;
    apiToken = prefs.getString("apiToken") ?? defaultToken;
    onboarded = prefs.getBool("onboarded") ?? false;
    try {
      apiKey = await const FlutterSecureStorage().read(key: "provider_api_key") ?? "";
    } catch (_) {
      apiKey = ""; // keychain unavailable (e.g. some CI/linux without libsecret)
    }
    reconnectClient();
    await refreshAll();
  }

  Future<void> refreshAll() async {
    await checkHealth();
    if (backendStatus != ConnectionStatus.connected) return;
    try {
      final results = await Future.wait([
        api.settings(),
        api.conversations(),
        api.documents(),
        api.tools(),
        api.jurisdictions(),
      ]);
      onboardedBackend = (results[0] as Map)["onboarded"] as bool? ?? false;
      conversations = ((results[1] as List)).cast<Conversation>();
      documents = ((results[2] as List)).cast<LegalDocument>();
      tools = ((results[3] as List)).cast<ToolDef>();
      jurisdictionData = results[4] as Map<String, dynamic>;
    } on ApiException {
      rethrow;
    }
    notifyListeners();
  }

  bool onboardedBackend = false;

  Future<bool> checkHealth() async {
    try {
      final h = await api.health();
      backendStatus =
          h["status"] == "ok" ? ConnectionStatus.connected : ConnectionStatus.offline;
    } catch (_) {
      backendStatus = ConnectionStatus.offline;
    }
    notifyListeners();
    return backendStatus == ConnectionStatus.connected;
  }

  // ----------------------------------------------------------- onboarding --

  Future<void> completeOnboarding({
    required String country,
    required String province,
    required String city,
    required String privacyPreference,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool("onboarded", true);
    onboarded = true;
    if (backendStatus == ConnectionStatus.connected) {
      await api.patchSettings({
        "onboarded": true,
        "country": country,
        "province": province,
        "city": city,
        "privacy_preference": privacyPreference,
      });
    }
    notifyListeners();
  }

  Future<void> skipForDemo() =>
      completeOnboarding(country: "United States", province: "California", city: "", privacyPreference: "local-first");

  // -------------------------------------------------------- conversations --

  Future<void> newChat() async {
    activeConversationId = null;
    messages = [];
    pendingSources = [];
    streamBuffer.clear();
    view = MainView.chat;
    notifyListeners();
  }

  void setView(MainView v) {
    view = v;
    notifyListeners();
  }

  void setMode(ChatMode m) {
    mode = m;
    if (view != MainView.chat && view != MainView.document) view = MainView.chat;
    notifyListeners();
  }

  void pushLocalMessage(Message m) {
    messages = [...messages, m];
    notifyListeners();
  }

  void updateMdxText(String text) {
    mdxText = text;
    notifyListeners();
  }

  void setDocSplitRatio(double ratio) {
    docSplitRatio = ratio.clamp(0.2, 0.8);
    notifyListeners();
  }

  Future<void> openConversation(String id) async {
    try {
      messages = await api.messages(id);
      activeConversationId = id;
      view = MainView.chat;
      notifyListeners();
    } on ApiException catch (e) {
      messages = [Message.assistant(e.message, mode, isError: true)];
      notifyListeners();
    }
  }

  Future<void> removeConversation(String id) async {
    await api.deleteConversation(id);
    conversations.removeWhere((c) => c.id == id);
    if (activeConversationId == id) await newChat();
    notifyListeners();
  }

  // ------------------------------------------------------------ messaging --

  WebSocketClient? _ws;
  StreamSubscription<WsEvent>? _wsSub;

  Future<void> send(String text, {bool asMdx = false, String? templateKey}) async {
    if (isStreaming || text.trim().isEmpty && templateKey == null) return;
    if (templateKey != null && text.isEmpty && !asMdx) {
      return _fetchTemplate(templateKey);
    }

    final userMsg = Message.user(text, mode);
    messages = [...messages, userMsg];
    final placeholder = Message.assistant("", mode, streaming: true);
    messages = [...messages, placeholder];
    streamBuffer.clear();
    pendingSources = [];
    research = ResearchProgress();
    isStreaming = true;
    notifyListeners();

    _ws = WebSocketClient(baseUrlWs: wsBase, token: apiToken);
    try {
      final events = _ws!.connect();
      _wsSub = events.listen((e) => _onEvent(e, placeholder), onError: (Object err) {
        _finishStream(placeholder, error: "Could not reach the Counsel AI backend at $baseUrl.");
      }, onDone: () {}, cancelOnError: true);

      await _ws!.sendTurn(
        turn: asMdx ? SendTurn.mdx : SendTurn.chat,
        message: text,
        mode: mode.wire,
        conversationId: activeConversationId,
        apiKey: apiKey.isNotEmpty ? apiKey : null,
        documentIds: attachedDocIds.toList(),
        template: templateKey,
      );
    } catch (e) {
      _finishStream(placeholder, error: "Connection failed: $e");
    }
  }

  Future<void> _fetchTemplate(String key) async {
    final placeholder = Message.assistant("", mode, streaming: true);
    messages = [...messages, placeholder];
    isStreaming = true;
    notifyListeners();
    _ws = WebSocketClient(baseUrlWs: wsBase, token: apiToken);
    final events = _ws!.connect();
    _wsSub = events.listen((e) => _onEvent(e, placeholder), onError: (Object e) {
      _finishStream(placeholder, error: "Could not reach the backend.");
    }, cancelOnError: true);
    await _ws!.sendTurn(
      turn: SendTurn.template,
      message: "",
      mode: mode.wire,
      conversationId: activeConversationId,
      template: key,
    );
  }

  void _onEvent(WsEvent e, Message placeholder) {
    switch (e.type) {
      case "conversation":
        activeConversationId = e.data["id"] as String?;
        final title = e.data["title"] as String? ?? "New conversation";
        if (!conversations.any((c) => c.id == activeConversationId)) {
          conversations.insert(0, Conversation(id: activeConversationId!, title: title));
        }
      case "status":
        research.detail = e.data["stage"] ?? "";
      case "research_progress":
        final stage = e.data["stage"] as String? ?? "";
        research.stage = stage;
        research.detail = e.data["detail"] as String? ?? "";
        research.completedStages.addAll(_stagesBefore(stage));
      case "token" || "mdx_token":
        streamBuffer.write(e.data["content"] ?? "");
        if (e.type == "mdx_token") {
          mdxText = streamBuffer.toString(); // live MDX rendering while streaming
        }
        placeholder.content = streamBuffer.toString();
      case "sources":
        pendingSources = ((e.data["sources"] as List?) ?? [])
            .whereType<Map<String, dynamic>>()
            .map(Source.fromJson)
            .toList();
        placeholder.sources = pendingSources;
      case "mdx_template":
        mdxText = (e.data["content"] as String?) ?? "";
        view = MainView.document;
      case "error":
        _finishStream(placeholder, error: (e.data["message"] as String?) ?? "Something went wrong.");
        return;
      case "done":
        _finishStream(placeholder);
        return;
    }
    notifyListeners();
  }

  Set<String> _stagesBefore(String stage) => switch (stage) {
        "searching" => {ResearchStage.planning},
        "reading" => {ResearchStage.planning, ResearchStage.searching},
        "writing" => {ResearchStage.planning, ResearchStage.searching, ResearchStage.reading},
        "done" => {
            ResearchStage.planning,
            ResearchStage.searching,
            ResearchStage.reading,
            ResearchStage.writing
          },
        _ => {},
      };

  Future<void> _finishStream(Message placeholder, {String? error}) async {
    isStreaming = false;
    placeholder.streaming = false;
    if (error != null) {
      placeholder
        ..content = error
        ..isError = true;
    } else {
      placeholder.content = streamBuffer.toString();
      if (placeholder.sources.isEmpty && pendingSources.isNotEmpty) {
        placeholder.sources = pendingSources;
      }
    }
    if (mode == ChatMode.research && research.stage.isNotEmpty) {
      research.completedStages.addAll({ResearchStage.writing});
    }
    await _wsSub?.cancel();
    await _ws?.close();
    _wsSub = null;
    _ws = null;
    streamBuffer.clear();
    notifyListeners();
  }

  // ------------------------------------------------------------- documents --

  Future<String?> uploadDocument(String path, String fileName) async {
    try {
      final doc = await api.uploadDocument(path);
      documents.insert(0, doc);
      attachedDocIds.add(doc.id);
      notifyListeners();
      return null;
    } on ApiException catch (e) {
      return e.message;
    } catch (e) {
      return "Upload failed: $e";
    }
  }

  void toggleAttachment(String docId) {
    attachedDocIds.contains(docId) ? attachedDocIds.remove(docId) : attachedDocIds.add(docId);
    notifyListeners();
  }

  Future<void> removeDocument(String id) async {
    await api.deleteDocument(id);
    documents.removeWhere((d) => d.id == id);
    attachedDocIds.remove(id);
    notifyListeners();
  }

  // ----------------------------------------------------------------- tools --

  Future<String> executeTool(String slug, Map<String, dynamic> input, {required bool confirmed}) async {
    try {
      final result = await api.toolExecute(slug, input, confirmed: confirmed);
      if (result["successful"] == true) {
        final data = jsonEncode(result["data"]);
        lastToolResult = data;
        return "";
      }
      return result["error"] as String? ?? "The action could not be completed.";
    } on ApiException catch (e) {
      return e.message;
    }
  }

  Future<Map<String, dynamic>> previewTool(String slug, Map<String, dynamic> input) =>
      api.toolPreview(slug, input);

  // ------------------------------------------------------------- settings --

  Future<void> saveServerConfig(String url, String token) async {
    final prefs = await SharedPreferences.getInstance();
    baseUrl = url.endsWith("/api") ? url.substring(0, url.length - 4) : url;
    apiToken = token;
    await prefs.setString("baseUrl", baseUrl);
    await prefs.setString("apiToken", apiToken);
    reconnectClient();
    await refreshAll();
  }

  Future<void> saveApiKey(String key) async {
    apiKey = key;
    try {
      await const FlutterSecureStorage().write(key: "provider_api_key", value: key);
    } catch (_) {/* keep in memory only */}
    notifyListeners();
  }

  @override
  void dispose() {
    _wsSub?.cancel();
    _ws?.close();
    super.dispose();
  }
}
