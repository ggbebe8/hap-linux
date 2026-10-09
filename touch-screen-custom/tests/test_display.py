"""Exercise the real persistent D-Bus client on an isolated test bus."""
import asyncio
import shutil
import subprocess
import threading
import time
from types import SimpleNamespace
import pytest
from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from touchgesture.display import DisplayMonitor, NAME, PATH
from touchgesture.rotation import StrokeOrientation
from touchgesture.recognition import Point
from touchgesture.config import load_config

SIGNATURE = 'ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv}'


@pytest.fixture
def service():
    if not shutil.which('dbus-daemon'):
        pytest.skip('dbus-daemon required for isolated integration test')
    daemon = subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    address = daemon.stdout.readline().strip()
    state = SimpleNamespace(calls=0, transform=0, serial=1, loop=None, bus=None, error=None)
    ready = threading.Event()
    async def run():
        state.loop = asyncio.get_running_loop()
        state.stop = asyncio.Event()
        bus = state.bus = await MessageBus(bus_address=address).connect()
        def handler(message):
            if message.message_type == MessageType.METHOD_CALL and message.member == 'GetCurrentState':
                state.calls += 1
                spec = ['eDP-1','vendor','panel','serial']
                body = [state.serial, [[spec,[],{'is-builtin':Variant('b',True)}]],
                        [[0,0,1.0,state.transform,True,[spec],{}]], {}]
                return Message.new_method_return(message,signature=SIGNATURE,body=body)
        bus.add_message_handler(handler)
        await bus.request_name(NAME)
        ready.set()
        try:
            await state.stop.wait()
        finally:
            bus.disconnect()
            await bus.wait_for_disconnect()
    def worker():
        try:
            asyncio.run(run())
        except Exception as exc:
            state.error = exc
            ready.set()
    thread = threading.Thread(target=worker,daemon=True)
    thread.start()
    assert ready.wait(3)
    assert state.error is None
    def rotate(transform):
        def send():
            state.transform = transform
            state.serial += 1
            state.bus.send(Message.new_signal(PATH,NAME,'MonitorsChanged'))
        state.loop.call_soon_threadsafe(send)
    state.rotate = rotate
    monitor = DisplayMonitor(address)
    try:
        yield monitor,state
    finally:
        monitor.close()
        state.loop.call_soon_threadsafe(state.stop.set)
        thread.join(timeout=3)
        daemon.terminate()
        daemon.communicate(timeout=3)


def eventually(predicate):
    deadline = time.monotonic()+3
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.005)
    pytest.fail('Timed out waiting for D-Bus signal processing')


def test_cached_reads_make_no_more_dbus_calls(service):
    monitor,server = service
    first = monitor.read()
    for _ in range(10000):
        assert monitor.read() is first
    assert server.calls == 1
    time.sleep(.05)
    assert server.calls == 1  # no background polling while idle


def test_signal_updates_state_and_cancels_active_stroke(service):
    monitor,server = service
    cfg = load_config()
    orientation = StrokeOrientation(cfg,monitor.read)
    orientation.begin()
    previous = monitor.read()
    server.rotate(1)
    def changed():
        try:
            return monitor.read().transform == 1
        except RuntimeError:
            return False
    eventually(changed)
    assert monitor.read().generation > previous.generation
    assert server.calls == 2
    assert orientation.finish([Point(.1,.1,0)]) is None
    orientation.begin()
    assert orientation.finish([Point(.1,.1,0)]) is not None
    assert server.calls == 2


def test_lost_service_does_not_reuse_stale_orientation(service):
    monitor,server = service
    monitor.read()
    server.loop.call_soon_threadsafe(server.bus.disconnect)
    def unavailable():
        try:
            monitor.read()
        except RuntimeError:
            return True
        return False
    eventually(unavailable)


def test_closed_monitor_releases_thread(service):
    monitor,_ = service
    monitor.read()
    monitor.close()
    assert not monitor.thread.is_alive()
    with pytest.raises(RuntimeError,match='closed'):
        monitor.read()


def test_unknown_connector_rejected(service):
    monitor,_ = service
    with pytest.raises(RuntimeError,match='identify'):
        monitor.read('HDMI-9')
