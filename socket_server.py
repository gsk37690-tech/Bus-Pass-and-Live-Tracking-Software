"""Newline-delimited JSON socket server bound to localhost only."""
import json
import socket
import threading


class LocalSocketServer:
    def __init__(self, service, host='127.0.0.1', port=0):
        self.service = service
        self.host = host
        self.port = port
        self.running = False
        self._socket = None
        self._thread = None

    def start(self):
        if self.running:
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(16)
        s.settimeout(0.4)
        self._socket = s
        self.port = s.getsockname()[1]
        self.running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while self.running:
            try:
                conn, _ = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        with conn:
            try:
                line = conn.makefile('rb').readline()
                if not line:
                    return
                request = json.loads(line.decode('utf-8'))
                action = request.get('action')

                if action == 'VALIDATE_QR':
                    result = self.service.validate(
                        request.get('payload', ''),
                        request.get('location', 'Main Gate')
                    )
                elif action == 'TRACK_EVENT':
                    result = {
                        'tracked': self.service.track(
                            request['pass_id'],
                            request.get('event', 'Pass Checked'),
                            request.get('location', 'Main Gate')
                        )
                    }
                elif action == 'CREATE_PASS':
                    result = self.service.create_pass(
                        name=request['name'],
                        passenger_id=request['passenger_id'],
                        expiry=request['expiry'],
                        pass_type=request.get('pass_type', 'Day Pass'),
                        phone=request.get('phone', ''),
                        email=request.get('email', ''),
                        fare=float(request.get('fare', 5.00))
                    )
                elif action == 'RENEW_PASS':
                    result = self.service.renew(request['pass_id'], request['expiry'])
                elif action == 'CANCEL_PASS':
                    result = self.service.cancel_pass(
                        request['pass_id'],
                        request.get('reason', 'User Request')
                    )
                elif action == 'GET_PASS':
                    result = self.service.get_pass(request['pass_id'])
                elif action == 'LIST_PASSES':
                    result = self.service.list_passes(
                        status=request.get('status'),
                        query=request.get('query')
                    )
                elif action == 'GET_STATS':
                    result = self.service.get_analytics()
                elif action == 'GET_ALERTS':
                    result = self.service.get_alerts(
                        unread_only=request.get('unread_only', False),
                        limit=request.get('limit', 50)
                    )
                elif action == 'MARK_ALERT_READ':
                    result = self.service.mark_alert_read(
                        alert_id=request.get('alert_id'),
                        mark_all=request.get('mark_all', False)
                    )
                else:
                    raise ValueError(f'Unknown action: {action}')
                response = {'ok': True, 'result': result}
            except Exception as e:
                response = {'ok': False, 'error': str(e)}

            try:
                conn.sendall((json.dumps(response, default=str) + '\n').encode('utf-8'))
            except OSError:
                pass

    def stop(self):
        self.running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass


def socket_request(port, request, timeout=3):
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as s:
        s.sendall((json.dumps(request) + '\n').encode('utf-8'))
        data = b''
        while b'\n' not in data:
            part = s.recv(4096)
            if not part:
                break
            data += part
    response = json.loads(data.decode('utf-8'))
    if not response.get('ok'):
        raise ValueError(response.get('error', 'Socket request failed'))
    return response['result']
