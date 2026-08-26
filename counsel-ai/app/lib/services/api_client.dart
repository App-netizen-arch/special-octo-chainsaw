/// REST client — the ONLY network surface of the app besides WebSockets.
/// The Flutter app never talks to any service other than the backend.
library;

import "dart:convert";

import "package:http/http.dart" as http;

import "../models/models.dart";

class ApiClient {
  ApiClient({required this.baseUrl, required this.token});

  final String baseUrl;
  final String token;

  Map<String, String> get _headers => {"X-API-Token": token};

  Uri _u(String path, [Map<String, dynamic>? query]) {
    final q = <String, dynamic>{...?query};
    return Uri.parse("$baseUrl$path").replace(queryParameters: _clean(q));
  }

  static Map<String, String>? _clean(Map<String, dynamic> q) {
    final out = <String, String>{};
    q.forEach((k, v) {
      if (v != null) out[k] = v.toString();
    });
    return out.isEmpty ? null : out;
  }

  Future<Map<String, dynamic>> health() async =>
      _json(await httpGet(_u("/api/health")));

  // ---------------------------------------------------------- conversations

  Future<List<Conversation>> conversations() async {
    final list = await _jsonList(await httpGet(_u("/api/conversations")));
    return list.whereType<Map<String, dynamic>>().map(Conversation.fromJson).toList();
  }

  Future<Conversation> createConversation(String title) async {
    final j = await _json(await httpPost(_u("/api/conversations", {"title": title})));
    return Conversation.fromJson(j);
  }

  Future<void> deleteConversation(String id) async =>
      httpDelete(_u("/api/conversations/$id"));

  Future<List<Message>> messages(String conversationId) async {
    final list =
        await _jsonList(await httpGet(_u("/api/conversations/$conversationId/messages")));
    return list.whereType<Map<String, dynamic>>().map(Message.fromJson).toList();
  }

  // ------------------------------------------------------------------ docs

  Future<List<LegalDocument>> documents() async {
    final list = await _jsonList(await httpGet(_u("/api/documents")));
    return list.whereType<Map<String, dynamic>>().map(LegalDocument.fromJson).toList();
  }

  Future<LegalDocument> uploadDocument(String filePath) async {
    final req = http.MultipartRequest("POST", _u("/api/documents"))
      ..headers.addAll(_headers)
      ..files.add(await http.MultipartFile.fromPath("file", filePath));
    final resp = await req.send().timeout(const Duration(minutes: 5));
    final body = jsonDecode(await resp.stream.bytesToString()) as Map<String, dynamic>;
    if (resp.statusCode >= 300) throw ApiException(_detail(body, resp.statusCode));
    return LegalDocument.fromJson(body);
  }

  Future<void> deleteDocument(String id) async => httpDelete(_u("/api/documents/$id"));

  Future<List<Source>> queryDocuments(String query, {int topK = 5}) async {
    final j = await _json(await httpPost(
      _u("/api/documents/query"),
      body: {"query": query, "top_k": topK},
    ));
    return (j as List).whereType<Map<String, dynamic>>().map(Source.fromJson).toList();
  }

  // ----------------------------------------------------------------- tools

  Future<List<ToolDef>> tools() async {
    final list = await _jsonList(await httpGet(_u("/api/tools")));
    return list.whereType<Map<String, dynamic>>().map(ToolDef.fromJson).toList();
  }

  Future<Map<String, dynamic>> toolPreview(String slug, Map<String, dynamic> input) async {
    final resp = await httpPost(_u("/api/tools/$slug/preview"), body: input);
    return _json(resp);
  }

  Future<Map<String, dynamic>> toolExecute(String slug, Map<String, dynamic> input,
      {required bool confirmed}) async {
    final resp = await httpPost(_u("/api/tools/$slug/execute"),
        body: {"input": input, "confirmed": confirmed});
    return _json(resp);
  }

  // -------------------------------------------------------------- settings

  Future<Map<String, dynamic>> settings() async => _json(await httpGet(_u("/api/settings")));

  Future<void> patchSettings(Map<String, dynamic> patch) async =>
      httpPatch(_u("/api/settings"), body: patch);

  Future<Map<String, dynamic>> jurisdictions() async =>
      _json(await httpGet(_u("/api/settings/jurisdictions")));

  // ------------------------------------------------------------- internals

  Future<http.Response> httpGet(Uri uri) => http
      .get(uri, headers: _headers)
      .timeout(const Duration(seconds: 15));

  Future<http.Response> httpPost(Uri uri, {Object? body}) => http
      .post(uri, headers: {..._headers, "Content-Type": "application/json"},
          body: jsonEncode(body ?? {}))
      .timeout(const Duration(seconds: 30));

  Future<http.Response> httpPatch(Uri uri, {Object? body}) => http
      .patch(uri, headers: {..._headers, "Content-Type": "application/json"},
          body: jsonEncode(body))
      .timeout(const Duration(seconds: 15));

  Future<http.Response> httpDelete(Uri uri) =>
      http.delete(uri, headers: _headers).timeout(const Duration(seconds: 15));

  Future<dynamic> _decode(http.Response resp) async {
    final text = utf8.decode(resp.bodyBytes);
    dynamic data;
    try {
      data = text.isEmpty ? {} : jsonDecode(text);
    } on FormatException {
      data = {"detail": text};
    }
    if (resp.statusCode >= 300) {
      throw ApiException(_detail(data is Map ? data : {}, resp.statusCode));
    }
    return data;
  }

  Future<Map<String, dynamic>> _json(http.Response resp) async {
    final d = await _decode(resp);
    if (d is List) return {"items": d};
    return d as Map<String, dynamic>;
  }

  Future<List<dynamic>> _jsonList(http.Response resp) async {
    final d = await _decode(resp);
    if (d is Map && d["items"] is List) return d["items"] as List;
    return d as List<dynamic>;
  }

  static String _detail(dynamic body, int status) {
    final detail = body is Map ? body["detail"] : null;
    if (detail is String && detail.isNotEmpty) return detail;
    return "Request failed ($status). Is the Counsel AI backend running?";
  }
}

class ApiException implements Exception {
  ApiException(this.message);
  final String message;
  @override
  String toString() => message;
}
