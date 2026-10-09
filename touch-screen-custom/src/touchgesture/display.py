"""One persistent session-bus connection; refresh only on display changes."""
import asyncio
from dataclasses import replace
import threading
from .rotation import parse_state

NAME = 'org.gnome.Mutter.DisplayConfig'
PATH = '/org/gnome/Mutter/DisplayConfig'


class DisplayMonitor:
    def __init__(self, bus_address=None):
        self.address = bus_address
        self.on_change = None
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.thread = None
        self.loop = self.task = None
        self.body = None
        self.cache = {}
        self.generation = 0
        self.error = 'Display state is not ready'

    def _invalidate(self, error='Display configuration is changing'):
        with self.lock:
            self.generation += 1
            self.body = None
            self.cache.clear()
            self.error = error
        callback = self.on_change
        if callback is not None:
            callback()

    def read(self, connector=None):
        if self.closed.is_set():
            raise RuntimeError('Display monitor is closed')
        if self.thread is None:
            self.thread = threading.Thread(target=self._worker, name='display-monitor', daemon=True)
            self.thread.start()
            if not self.ready.wait(4):
                self.close()
                raise RuntimeError('GNOME display connection timed out; use --rotation 0/90/180/270')
        with self.lock:
            if self.body is None:
                raise RuntimeError(f'{self.error}; use --rotation 0/90/180/270 if GNOME is unavailable')
            if connector not in self.cache:
                self.cache[connector] = replace(parse_state({'data': self.body}, connector),
                                                generation=self.generation)
            return self.cache[connector]

    def _worker(self):
        try:
            asyncio.run(self._run())
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._invalidate(f'Cannot monitor GNOME display: {exc}')
        finally:
            if self.body is not None:
                self._invalidate('GNOME display connection closed')
            self.ready.set()

    async def _run(self):
        from dbus_next import Message, MessageType
        from dbus_next.aio import MessageBus
        self.loop = asyncio.get_running_loop()
        self.task = asyncio.current_task()
        if self.closed.is_set():
            return
        bus = MessageBus(bus_address=self.address)
        updater = None
        dirty = asyncio.Event()

        async def call(message):
            reply = await asyncio.wait_for(bus.call(message), 2)
            if reply is None or reply.message_type == MessageType.ERROR:
                raise RuntimeError(f'D-Bus request failed: {getattr(reply, "body", None)}')
            return reply

        def on_message(message):
            if message.message_type != MessageType.SIGNAL:
                return
            changed = message.interface == NAME and message.path == PATH and message.member == 'MonitorsChanged'
            owner_changed = (message.sender == 'org.freedesktop.DBus' and
                             message.interface == 'org.freedesktop.DBus' and
                             message.member == 'NameOwnerChanged' and message.body[0] == NAME)
            if changed or owner_changed:
                self._invalidate()
                dirty.set()

        async def update():
            while True:
                await dirty.wait()
                dirty.clear()
                with self.lock:
                    generation = self.generation
                try:
                    reply = await call(Message(destination=NAME, path=PATH, interface=NAME,
                                               member='GetCurrentState'))
                    with self.lock:
                        # Never publish a reply overtaken by another change signal.
                        if generation == self.generation:
                            self.body = reply.body
                            self.cache.clear()
                except Exception as exc:
                    self._invalidate(f'Cannot read GNOME display: {exc}')
                self.ready.set()

        try:
            await asyncio.wait_for(bus.connect(), 2)
            bus.add_message_handler(on_message)
            for rule in (
                f"type='signal',sender='{NAME}',interface='{NAME}',path='{PATH}',member='MonitorsChanged'",
                f"type='signal',sender='org.freedesktop.DBus',interface='org.freedesktop.DBus',member='NameOwnerChanged',arg0='{NAME}'",
            ):
                await call(Message(destination='org.freedesktop.DBus', path='/org/freedesktop/DBus',
                                   interface='org.freedesktop.DBus', member='AddMatch', signature='s', body=[rule]))
            dirty.set()
            updater = asyncio.create_task(update())
            await bus.wait_for_disconnect()
        finally:
            self._invalidate('GNOME display connection closed')
            if updater is not None:
                updater.cancel()
                await asyncio.gather(updater, return_exceptions=True)
            bus.disconnect()

    def close(self):
        self.closed.set()
        if self.loop is not None and self.task is not None:
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:  # Event loop already closed following disconnect.
                pass
        if self.thread is not None:
            self.thread.join(timeout=3)
        self._invalidate('Display monitor is closed')
