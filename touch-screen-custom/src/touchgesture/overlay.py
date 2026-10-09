"""Use the GNOME Shell extension as the preview renderer."""
from .notification import NotificationPreview


class OverlayPreview(NotificationPreview):
    destination = 'org.gnome.Shell'
    object_path = '/org/gnome/Shell/Extensions/Touchgesture'
    interface = 'org.gnome.Shell.Extensions.Touchgesture'

    async def send_show(self, call, text, duration_ms, handle):
        try:
            await call('Show', 'ssu', [text[0], text[1], duration_ms])
        except RuntimeError as exc:
            raise RuntimeError('중앙 UI 확장을 활성화하세요: ./install-overlay.sh (첫 설치 후 로그아웃/로그인이 필요할 수 있습니다)') from exc
        return 1

    async def send_hide(self, call, handle):
        await call('Hide', '', [])
