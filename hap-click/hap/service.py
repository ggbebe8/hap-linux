"""Session D-Bus service. AT-SPI actions and validation for Shell click fallback."""
import json
import signal
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from gi.repository import Gio, GLib
from .accessibility import Accessibility

BUS = 'io.github.haplinux.Controller'
PATH = '/io/github/haplinux/Controller'
XML = '''<node><interface name="io.github.haplinux.Controller">
<method name="Scan"><arg type="u" direction="in" name="pid"/><arg type="s" direction="in" name="title"/><arg type="s" direction="out" name="result"/></method>
<method name="Activate"><arg type="s" direction="in" name="session"/><arg type="s" direction="in" name="label"/><arg type="b" direction="out" name="success"/></method>
<method name="PrepareClick"><arg type="s" direction="in" name="session"/><arg type="s" direction="in" name="label"/><arg type="d" direction="out" name="x"/><arg type="d" direction="out" name="y"/></method>
<method name="Cancel"><arg type="s" direction="in" name="session"/></method>
<method name="Ping"><arg type="s" direction="out" name="version"/></method>
</interface></node>'''


class Service:
    def __init__(self, connection):
        self.connection = connection
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='atspi')
        self.backend = Accessibility()
        self.session = None
        self.busy = False
        self.registration = connection.register_object(PATH, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], self.call, None, None)

    def cancel(self):
        if self.session:
            self.session['cancelled'].set()
            self.session = None

    def submit(self, invocation, job, done):
        self.busy = True
        future = self.pool.submit(job)
        def finish():
            self.busy = False
            try:
                done(future.result())
            except Exception as error:
                invocation.return_dbus_error(BUS + '.Error', str(error))
            return GLib.SOURCE_REMOVE
        future.add_done_callback(lambda _: GLib.idle_add(finish))

    def call(self, connection, sender, path, interface, method, parameters, invocation):
        args = parameters.unpack()
        try:
            if method == 'Ping':
                invocation.return_value(GLib.Variant('(s)', ('1.0',)))
            elif method == 'Cancel':
                if self.session and self.session['owner'] == sender and (not args[0] or args[0] == self.session['id']):
                    self.cancel()
                invocation.return_value(None)
            elif method == 'Scan':
                if self.busy:
                    raise RuntimeError('이전 AT-SPI 요청을 처리 중입니다. 잠시 후 다시 시도하세요.')
                self.cancel()
                session = dict(id=uuid.uuid4().hex, owner=sender, cancelled=threading.Event(), refs={}, expires=time.monotonic() + 30)
                self.session = session
                def complete(result):
                    if self.session is not session:
                        raise RuntimeError('취소된 탐색입니다.')
                    payload, session['refs'] = result
                    payload['session'] = session['id']
                    invocation.return_value(GLib.Variant('(s)', (json.dumps(payload),)))
                self.submit(invocation, lambda: self.backend.scan(*args, session['cancelled']), complete)
            elif method in ('Activate', 'PrepareClick'):
                session = self.session
                if not session or session['owner'] != sender or session['id'] != args[0] or time.monotonic() > session['expires']:
                    raise RuntimeError('선택 세션이 만료되었습니다.')
                if self.busy or args[1] not in session['refs']:
                    raise RuntimeError('유효하지 않은 선택입니다.')
                target = session['refs'].pop(args[1])
                session['refs'].clear()  # a session can activate exactly once
                def complete(result):
                    if self.session is session:
                        self.cancel()
                    invocation.return_value(GLib.Variant('(dd)', result) if method == 'PrepareClick'
                                            else GLib.Variant('(b)', (result,)))
                operation = self.backend.prepare_click if method == 'PrepareClick' else self.backend.activate
                self.submit(invocation, lambda: operation(target, session['cancelled']), complete)
            else:
                raise RuntimeError('알 수 없는 메서드입니다.')
        except Exception as error:
            invocation.return_dbus_error(BUS + '.Error', str(error))


def main():
    loop = GLib.MainLoop()
    services = []
    def acquired(connection, _name):
        services.append(Service(connection))
    owner = Gio.bus_own_name(Gio.BusType.SESSION, BUS, Gio.BusNameOwnerFlags.NONE, acquired, None, lambda *_: loop.quit())
    for sig in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1])
    try:
        loop.run()
    finally:
        for service in services:
            service.cancel()
            service.pool.shutdown(wait=False, cancel_futures=True)
        Gio.bus_unown_name(owner)


if __name__ == '__main__':
    main()
