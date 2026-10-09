"""Desktop notification protocol tested without touching the user's desktop."""
import asyncio
import shutil
import subprocess
import threading
import time
from types import SimpleNamespace
import pytest
from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus
from touchgesture.notification import NotificationPreview, NAME
from touchgesture.overlay import OverlayPreview


@pytest.fixture
def notification_service(request):
    renderer = getattr(request, "param", NotificationPreview)
    if not shutil.which('dbus-daemon'):
        pytest.skip('dbus-daemon required')
    daemon = subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    address = daemon.stdout.readline().strip()
    state = SimpleNamespace(calls=[],delay=0,error=None)
    ready = threading.Event()
    async def run():
        state.loop = asyncio.get_running_loop()
        state.stop = asyncio.Event()
        bus = await MessageBus(bus_address=address).connect()
        def handler(msg):
            if msg.message_type != MessageType.METHOD_CALL or msg.interface != renderer.interface:
                return
            state.calls.append((msg.member,msg.body))
            reply = Message.new_method_return(msg,'u',[42]) if msg.member == 'Notify' else Message.new_method_return(msg)
            if msg.member == 'Notify' and state.delay:
                async def delayed():
                    await asyncio.sleep(state.delay)
                    await bus.send(reply)
                asyncio.create_task(delayed())
                return True
            return reply
        bus.add_message_handler(handler)
        await bus.request_name(renderer.destination)
        ready.set()
        await state.stop.wait()
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
    assert ready.wait(3) and state.error is None
    ui = renderer(address)
    try:
        yield ui,state
    finally:
        ui.close()
        state.loop.call_soon_threadsafe(state.stop.set)
        thread.join(3)
        daemon.terminate()
        daemon.communicate(timeout=3)


def wait_for(predicate):
    deadline = time.monotonic()+3
    while time.monotonic()<deadline:
        if predicate():
            return
        time.sleep(.005)
    pytest.fail('notification operation timed out')


def test_one_show_no_repeated_ipc_and_hide(notification_service):
    ui,s = notification_service
    for _ in range(1000):
        ui.show(('손을 떼면: 탭 닫기','↓→ · CTRL+W'),1.5)
    wait_for(lambda:len(s.calls)==1)
    method,body = s.calls[0]
    assert method == 'Notify' and body[1] == 0
    assert body[6]['transient'].value and body[6]['suppress-sound'].value
    ui.show()
    wait_for(lambda:len(s.calls)==2)
    assert s.calls[-1] == ('CloseNotification',[42])


def test_replace_does_not_stack_notifications(notification_service):
    ui,s = notification_service
    ui.show(('one','a'),1.5)
    wait_for(lambda:len(s.calls)==1)
    ui.show(('two','b'),1.5)
    wait_for(lambda:len(s.calls)==2)
    assert s.calls[-1][1][1] == 42


def test_timeout_hides_without_more_touch_events(notification_service):
    ui,s = notification_service
    ui.show(('one','a'),.1)
    wait_for(lambda:len(s.calls)>=2)
    assert [m for m,_ in s.calls] == ['Notify','CloseNotification']


def test_lift_while_notify_pending_closes_returned_id(notification_service):
    ui,s = notification_service
    s.delay = .1
    ui.show(('one','a'),1)
    wait_for(lambda:len(s.calls)==1)
    ui.show()
    wait_for(lambda:len(s.calls)==2)
    assert s.calls[-1] == ('CloseNotification',[42])


def test_shutdown_closes_banner_and_thread(notification_service):
    ui,s = notification_service
    ui.show(('one','a'),1.5)
    wait_for(lambda:len(s.calls)==1)
    ui.close()
    assert s.calls[-1] == ('CloseNotification',[42])
    assert not ui.thread.is_alive()


@pytest.mark.parametrize('notification_service',[OverlayPreview],indirect=True)
def test_overlay_uses_shell_show_hide_without_notifications(notification_service):
    ui,s = notification_service
    for _ in range(1000):
        ui.show(('손을 떼면: 탭 닫기','1손가락 ↓→ · CTRL+W'),1.5)
    wait_for(lambda:len(s.calls)==1)
    assert s.calls[0][0] == 'Show'
    assert s.calls[0][1][:2] == ['손을 떼면: 탭 닫기','1손가락 ↓→ · CTRL+W']
    assert 0 < s.calls[0][1][2] <= 1500
    ui.show()
    wait_for(lambda:len(s.calls)==2)
    assert s.calls[-1] == ('Hide',[])


@pytest.mark.parametrize('notification_service',[OverlayPreview],indirect=True)
def test_overlay_timeout_and_shutdown(notification_service):
    ui,s = notification_service
    ui.show(('one','↓'),.1)
    wait_for(lambda:len(s.calls)>=2)
    assert [m for m,_ in s.calls] == ['Show','Hide']
    ui.show(('two','↑'),1.5)
    wait_for(lambda:len(s.calls)==3)
    ui.close()
    assert s.calls[-1] == ('Hide',[])
    assert not ui.thread.is_alive()
