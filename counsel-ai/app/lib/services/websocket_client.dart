/// WebSocket client for streaming chat / research events.
///
/// One-shot connection per turn keeps lifecycle handling trivial and robust;
/// the backend protocol is a sequence of JSON frames:
///   {type: conversation|status|research_progress|token|mdx_token|sources|
///          mdx_template|tool_preview|tool_result|done|error, ...}
library;

import "dart:async";
import "dart:convert";

import "package:web_socket_channel/web_socket_channel.dart";

class WsEvent {
  final String type;
  final Map<String, dynamic> data;
  WsEvent(this.type, this.data);

  static WsEvent parse(dynamic raw) {
    final j = raw is String ? jsonDecode(raw) as Map<String, dynamic> : raw as Map<String, dynamic>;
    return WsEvent((j["type"] as String?) ?? "unknown", j);
  }
}

enum SendTurn { chat, mdx, template }

class WebSocketClient {
  WebSocketClient({required this.baseUrlWs, required this.token});

  /// ws://host:port
  final String baseUrlWs;
  final String token;

  WebSocketChannel? _channel;

  Stream<WsEvent> connect() {
    final uri = Uri.parse("$baseUrlWs/ws?token=$token");
    _channel = WebSocketChannel.connect(uri);
    return _channel!.stream.map(WsEvent.parse);
  }

  Future<void> sendTurn({
    required SendTurn turn,
    required String message,
    required String mode,
    String? conversationId,
    String? apiKey,
    List<String> documentIds = const [],
    String? template,
  }) async {
    final payload = <String, dynamic>{
      "type": "chat",
      "message": message,
      "mode": mode,
      if (conversationId != null) "conversation_id": conversationId,
      if (apiKey != null && apiKey.isNotEmpty) "api_key": apiKey,
      "document_ids": documentIds,
      "mdx": turn == SendTurn.mdx,
      if (template != null) "template": template,
    };
    _channel?.sink.add(jsonEncode(payload));
  }

  Future<void> close() async {
    await _channel?.sink.close();
    _channel = null;
  }
}
