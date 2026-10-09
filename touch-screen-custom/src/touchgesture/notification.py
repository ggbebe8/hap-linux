"""Transient, silent desktop preview; never blocks the input thread."""
import asyncio
import logging
import threading
import time
from html import escape

log = logging.getLogger(__name__)
NAME = 'org.freedesktop.Notifications'
PATH = '/org/freedesktop/Notifications'


class NotificationPreview:
    destination = NAME
    object_path = PATH
    interface = NAME

    async def send_show(self, call, text, duration_ms, handle):
        from dbus_next import Variant
        reply = await call('Notify', 'susssasa{sv}i', [
            'touchgesture', handle, 'input-touchpad-symbolic', text[0], escape(text[1]), [],
            {'transient': Variant('b', True), 'suppress-sound': Variant('b', True),
             'urgency': Variant('y', 1)}, duration_ms])
        return reply.body[0]

    async def send_hide(self, call, handle):
        await call('CloseNotification', 'u', [handle])

    def __init__(self, bus_address=None):
        self.address = bus_address
        self.lock = threading.Lock()
        self.desired = None
        self.closed = False
        self.failed = False
        self.thread = None
        self.loop = self.changed = None

    def show(self, text=None, duration=0):
        with self.lock:
            if self.closed or self.failed:
                return
            content = None if text is None or duration <= 0 else (text, time.monotonic()+duration)
            if (self.desired is None and content is None) or (self.desired and content and self.desired[0] == content[0]):
                return
            self.desired = content
            if self.thread is None and content is not None:
                self.thread = threading.Thread(target=self._worker, name='gesture-preview', daemon=True)
                self.thread.start()
        self._wake()

    def _wake(self):
        if self.loop is not None and self.changed is not None:
            try:
                self.loop.call_soon_threadsafe(self.changed.set)
            except RuntimeError:
                pass

    def _worker(self):
        try:
            asyncio.run(self._run())
        except Exception as exc:
            log.warning('Gesture preview unavailable: %s (gestures still work)', exc)
            with self.lock:
                self.failed = True

    async def _run(self):
        from dbus_next import Message, MessageType
        from dbus_next.aio import MessageBus
        self.loop = asyncio.get_running_loop()
        self.changed = asyncio.Event()
        bus = MessageBus(bus_address=self.address)
        notification_id = 0
        displayed = None
        disconnected = None

        async def call(member, signature, body):
            reply = await asyncio.wait_for(bus.call(Message(destination=self.destination, path=self.object_path,
                interface=self.interface, member=member, signature=signature, body=body)), 1)
            if reply is None or reply.message_type == MessageType.ERROR:
                raise RuntimeError(f'{member}: {getattr(reply, "body", None)}')
            return reply

        try:
            await asyncio.wait_for(bus.connect(), 1)
            disconnected = asyncio.create_task(bus.wait_for_disconnect())
            disconnected.add_done_callback(lambda _: self.changed.set())
            while True:
                self.changed.clear()
                with self.lock:
                    desired, closed = self.desired, self.closed
                if disconnected.done():
                    raise RuntimeError('notification connection closed')
                if desired is not None and desired[1] <= time.monotonic():
                    with self.lock:
                        if self.desired == desired:
                            self.desired = None
                    continue
                if desired is None or closed:
                    if notification_id:
                        await self.send_hide(call, notification_id)
                        notification_id, displayed = 0, None
                    if closed:
                        return
                elif displayed != desired[0]:
                    notification_id = await self.send_show(call, desired[0],
                        max(1, int((desired[1]-time.monotonic())*1000)), notification_id)
                    displayed = desired[0]
                    # A lift/cancel may have arrived while Notify was in flight.
                    continue
                timeout = max(0, desired[1]-time.monotonic()) if desired else None
                try:
                    await asyncio.wait_for(self.changed.wait(), timeout)
                except asyncio.TimeoutError:
                    pass
        finally:
            if notification_id and bus.connected:
                try:
                    await self.send_hide(call, notification_id)
                except Exception:
                    pass
            bus.disconnect()
            if disconnected is not None:
                await asyncio.gather(disconnected, return_exceptions=True)

    def close(self):
        with self.lock:
            self.closed = True
            self.desired = None
        self._wake()
        if self.thread is not None:
            self.thread.join(timeout=3)
