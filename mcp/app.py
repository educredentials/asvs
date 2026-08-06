import json
import uuid
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from .schema import TOOLS
from . import tools

User = get_user_model()


def _authenticate_request(request):
    auth_header = request.headers.get('Authorization', '')
    token = None
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    elif auth_header.startswith('Token '):
        token = auth_header[6:]
    if not token:
        raise AuthenticationFailed('Authorization header missing or empty.')
    try:
        from rest_framework.authtoken.models import Token
        t = Token.objects.get(key=token)
        request.user = t.user
        request.token = t
    except Token.DoesNotExist:
        raise AuthenticationFailed('Invalid or expired API token.')


def _make_session_id(request):
    return request.headers.get('X-Session-Id', str(uuid.uuid4()))


def _sse_event(event_type, data):
    body = json.dumps(data, default=str)
    lines = [
        f'event: {event_type}',
        f'data: {body}',
        '',
        '',
    ]
    return '\n'.join(lines).encode('utf-8') + b'\n'


def sse_heartbeat():
    return b': heartbeat\n\n'


@csrf_exempt
def mcp_endpoint(request):
    try:
        _authenticate_request(request)
    except AuthenticationFailed as e:
        return JsonResponse({"error": str(e)}, status=401)

    session_id = _make_session_id(request)

    if request.method == 'GET':
        """SSE endpoint for server-to-client notifications."""
        def event_stream():
            # Send initial open event
            yield _sse_event('open', {'session': session_id})
            i = 0
            while True:
                yield sse_heartbeat()
                i += 1
                if i > 10:
                    break  # Keep connection alive briefly, then close

        resp = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
        )
        resp['Mcp-Session-Id'] = session_id
        resp['Cache-Control'] = 'no-cache'
        resp['Connection'] = 'keep-alive'
        return resp

    if request.method == 'OPTIONS':
        """CORS preflight / probe."""
        resp = JsonResponse({}, status=204)
        return resp

    if request.method == 'POST':
        raw_body = request.body
        if not raw_body.strip():
            return JsonResponse({"error": "Empty request body"}, status=400)
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': None,
                'error': {'code': -32700, 'message': f'Parse error: {str(e)}'},
            }, status=400)

        if not isinstance(body, dict):
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': None,
                'error': {'code': -32600, 'message': 'Invalid request: expected JSON object'},
            }, status=400)

        method = body.get('method')
        params = body.get('params') or {}
        id_ = body.get('id')

        # Notifications have no id — accept and fire-and-forget
        if id_ is None:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': None,
                'result': {},
            })

        if method == 'initialize':
            result = {
                'protocolVersion': '2025-03-26',
                'capabilities': {
                    'tools': {},
                    'logging': {},
                },
                'serverInfo': {
                    'name': 'ASVS-MCP',
                    'version': '1.0.0',
                }
            }
            resp = JsonResponse({
                'jsonrpc': '2.0',
                'id': id_,
                'result': result,
            })
            resp['Mcp-Session-Id'] = session_id
            return resp

        if method in ('listTools', 'tools/list'):
            tools_list = [
                {'name': t['name'], 'description': t['description'], 'inputSchema': t['inputSchema']}
                for t in TOOLS
            ]
            resp = JsonResponse({
                'jsonrpc': '2.0',
                'id': id_,
                'result': {'tools': tools_list},
            })
            resp['Mcp-Session-Id'] = session_id
            return resp

        if method in ('callTool', 'tools/call'):
            tool_name = params.get('name')
            tool_params = params.get('arguments', {})
            if not tool_name:
                resp = JsonResponse({
                    'jsonrpc': '2.0',
                    'id': id_,
                    'error': {'code': -32602, 'message': 'Missing tool name'},
                })
            else:
                try:
                    result = dispatch_tool(request, tool_name, tool_params)
                    resp = JsonResponse({
                        'jsonrpc': '2.0',
                        'id': id_,
                        'result': {
                            'content': [
                                {'type': 'text', 'text': json.dumps(result, default=str)}
                            ]
                        },
                    })
                except Exception as e:
                    resp = JsonResponse({
                        'jsonrpc': '2.0',
                        'id': id_,
                        'error': {'code': -32000, 'message': str(e)},
                    })
            resp['Mcp-Session-Id'] = session_id
            return resp

        if method == 'ping':
            resp = JsonResponse({
                'jsonrpc': '2.0',
                'id': id_,
                'result': {'notificationsSent': True},
            })
            resp['Mcp-Session-Id'] = session_id
            return resp

        # Unknown method with id → JSON-RPC error
        return JsonResponse({
            'jsonrpc': '2.0',
            'id': id_,
            'error': {'code': -32601, 'message': f'Method not found: {method}'},
        }, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)


def dispatch_tool(request, tool_name, params):
    fn = getattr(tools, tool_name, None)
    if not fn:
        raise ValueError(f"Unknown tool: {tool_name}")
    return fn(request, params or {})
