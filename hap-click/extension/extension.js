import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const BUS = 'io.github.haplinux.Controller';
const PATH = '/io/github/haplinux/Controller';

export default class HapExtension extends Extension {
    enable() {
        this._enabled = true;
        this._generation = 0;
        this._signals = [];
        this._settings = this.getSettings();
        this._pointer = global.stage.context.get_backend().get_default_seat()
            .create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
        Main.wm.addKeybinding('show-hints', this._settings, Meta.KeyBindingFlags.IGNORE_AUTOREPEAT,
            Shell.ActionMode.NORMAL, () => {
                try {
                    this._toggle();
                } catch (error) {
                    this._close();
                    Main.notify('HAP Linux', error.message);
                    console.error(error);
                }
            });
        this._modeSignal = Main.sessionMode.connect('updated', () => this._close());
    }

    _call(method, signature, values, callback = null) {
        Gio.DBus.session.call(BUS, PATH, BUS, method, new GLib.Variant(signature, values),
            null, Gio.DBusCallFlags.NONE, 6500, null, (connection, result) => {
                try {
                    const reply = connection.call_finish(result).deepUnpack();
                    callback?.(reply, null);
                } catch (error) {
                    callback?.(null, error);
                }
            });
    }

    _toggle() {
        this._stopClick();
        if (this._overlay) {
            this._close();
            return;
        }
        const win = global.display.focus_window;
        if (!win || Main.overview.visible || Main.sessionMode.isLocked)
            return;
        this._window = win;
        this._prefix = '';
        this._hints = [];
        this._session = null;
        const generation = ++this._generation;
        this._overlay = new St.Widget({reactive: true, can_focus: true,
            layout_manager: new Clutter.FixedLayout(),
            x: 0, y: 0, width: global.stage.width, height: global.stage.height});
        Main.layoutManager.addTopChrome(this._overlay, {trackFullscreen: false});
        this._status = new St.Label({style_class: 'hap-status', text: 'HAP · 탐색 중… · Esc 취소'});
        const monitor = Main.layoutManager.monitors[win.get_monitor()];
        this._status.set_position(monitor.x + 24, monitor.y + 48);
        this._overlay.add_child(this._status);
        this._overlay.connect('key-press-event', (_actor, event) => this._key(event));
        this._overlay.connect('button-press-event', () => { this._close(); return Clutter.EVENT_STOP; });
        this._grab = Main.pushModal(this._overlay, {actionMode: Shell.ActionMode.POPUP});
        if (this._grab.is_revoked()) {
            this._close();
            Main.notify('HAP Linux', '키보드를 확보하지 못했습니다. 열린 메뉴를 닫고 다시 시도하세요.');
            return;
        }
        const initialFrame = win.get_frame_rect();
        this._signals.push([win, win.connect('unmanaged', () => this._close())]);
        for (const signal of ['position-changed', 'size-changed'])
            this._signals.push([win, win.connect(signal, () => {
                const current = win.get_frame_rect();
                if (['x', 'y', 'width', 'height'].some(k => initialFrame[k] !== current[k]))
                    this._close();
            })]);
        this._signals.push([global.display, global.display.connect('notify::focus-window', () => {
            if (global.display.focus_window !== this._window)
                this._close();
        })]);
        this._timeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 25000, () => {
            this._timeout = 0;
            this._close();
            return GLib.SOURCE_REMOVE;
        });
        this._call('Scan', '(us)', [win.get_pid(), win.get_title() ?? ''], (reply, error) => {
            if (!this._enabled || generation !== this._generation)
                return;
            if (error) {
                this._close();
                Main.notify('HAP Linux', error.message);
                return;
            }
            try {
                const payload = JSON.parse(reply[0]);
                this._session = payload.session;
                if (!payload.hints.length) {
                    this._close();
                    Main.notify('HAP Linux', '이 창에서 실행 가능한 AT-SPI 요소를 찾지 못했습니다.');
                    return;
                }
                this._bounds = payload.bounds;
                const geometry = this._coordinateRect(win, payload.bounds);
                this._hints = payload.hints.map(hint => {
                    const actor = new St.Label({text: hint.label, style_class: 'hap-hint'});
                    const [x, y] = this._hintPoint(geometry, [hint.x, hint.y]);
                    actor.set_position(x - 12, y - 10);
                    this._overlay.add_child(actor);
                    return {...hint, actor};
                });
                this._truncated = payload.truncated;
                this._updateStatus();
            } catch (error) {
                this._close();
                Main.notify('HAP Linux', error.message);
            }
        });
    }

    _key(event) {
        const key = event.get_key_symbol();
        if (key === Clutter.KEY_Escape) {
            this._close();
            return Clutter.EVENT_STOP;
        }
        if (!this._session)
            return Clutter.EVENT_STOP;
        if (key === Clutter.KEY_BackSpace) {
            this._prefix = this._prefix.slice(0, -1);
        } else {
            const unicode = Clutter.keysym_to_unicode(key);
            const letter = unicode ? String.fromCodePoint(unicode).toUpperCase() : '';
            if (!'ASDFJKL'.includes(letter) || !letter)
                return Clutter.EVENT_STOP;
            const prefix = this._prefix + letter;
            if (!this._hints.some(hint => hint.label.startsWith(prefix)))
                return Clutter.EVENT_STOP;
            this._prefix = prefix;
        }
        const selected = this._hints.find(hint => hint.label === this._prefix);
        if (selected) {
            const session = this._session;
            const win = this._window;
            const frame = win.get_frame_rect();
            const title = win.get_title();
            const bounds = this._bounds;
            // Pop the modal grab before sending the AT-SPI action.
            this._close(false);
            const generation = this._generation;
            this._call(selected.pointer ? 'PrepareClick' : 'Activate', '(ss)', [session, selected.label], (reply, error) => {
                if (!this._enabled || generation !== this._generation)
                    return;
                if (error) {
                    Main.notify('HAP Linux', error.message);
                    return;
                }
                if (selected.pointer) {
                    const current = win.get_frame_rect();
                    if (global.display.focus_window !== win || Main.overview.visible || Main.sessionMode.isLocked ||
                        win.get_title() !== title || ['x', 'y', 'width', 'height'].some(k => frame[k] !== current[k])) {
                        Main.notify('HAP Linux', '활성 창이 변경되었습니다. 다시 탐색하세요.');
                        return;
                    }
                    this._clickItem(win, frame, reply, bounds);
                } else if (!reply[0]) {
                    Main.notify('HAP Linux', '앱이 선택한 요소의 실행을 거부했습니다.');
                }
            });
        } else {
            for (const hint of this._hints)
                hint.actor.visible = hint.label.startsWith(this._prefix);
            this._updateStatus();
        }
        return Clutter.EVENT_STOP;
    }

    _updateStatus() {
        const example = this._hints.find(h => h.label.startsWith(this._prefix))?.label ?? '';
        this._status.text = `HAP · ${this._hints.length}개${this._truncated ? ' (일부)' : ''}` +
            ` · 입력: ${this._prefix || '—'} · ${example.length}글자 입력 (예: ${example}) · Esc 취소`;
    }

    _coordinateRect(win, bounds) {
        const frame = win.get_frame_rect();
        const buffer = win.get_buffer_rect();
        // Chromium's accessible root includes client-side shadows. GTK may
        // instead expose just the visible frame. Compare dimensions, never
        // treat a Wayland client's SCREEN origin as a desktop position.
        const error = rect => Math.abs(rect.width - bounds.width) + Math.abs(rect.height - bounds.height);
        return bounds && error(buffer) < error(frame) && error(buffer) <= 4 ? buffer : frame;
    }

    _hintPoint(frame, point) {
        if (!point.every(v => Number.isFinite(v) && v >= 0 && v <= 1))
            throw new Error('클릭 좌표가 유효하지 않습니다.');
        return [frame.x + point[0] * frame.width, frame.y + point[1] * frame.height];
    }

    _clickItem(win, frame, point, bounds) {
        const geometry = this._coordinateRect(win, bounds);
        const [x, y] = this._hintPoint(geometry, point);
        if (x < frame.x || y < frame.y || x >= frame.x + frame.width || y >= frame.y + frame.height)
            throw new Error('창 밖의 요소는 클릭할 수 없습니다. 다시 탐색하세요.');
        let clicks = 1;
        // Nautilus file items open with a double click unless configured otherwise.
        if (win.get_gtk_application_id() === 'org.gnome.Nautilus') {
            const schema = Gio.SettingsSchemaSource.get_default().lookup('org.gnome.nautilus.preferences', true);
            clicks = schema && new Gio.Settings({settings_schema: schema}).get_string('click-policy') === 'single' ? 1 : 2;
        }
        this._pointer.notify_absolute_motion(GLib.get_monotonic_time(), x, y);
        const title = win.get_title();
        let step = 0;
        // Let Mutter deliver the motion and remove the overlay's input region
        // before pressing. Separate events so GTK observes each button state.
        this._clickTimeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, () => {
            const current = win.get_frame_rect();
            if (!this._enabled || global.display.focus_window !== win || Main.overview.visible || Main.sessionMode.isLocked ||
                win.get_title() !== title || ['x', 'y', 'width', 'height'].some(k => current[k] !== frame[k])) {
                this._clickTimeout = 0;
                this._stopClick();
                return GLib.SOURCE_REMOVE;
            }
            this._pointerPressed = step % 2 === 0;
            this._pointer.notify_button(GLib.get_monotonic_time(), Clutter.BUTTON_PRIMARY,
                this._pointerPressed ? Clutter.ButtonState.PRESSED : Clutter.ButtonState.RELEASED);
            if (++step === clicks * 2) {
                this._clickTimeout = 0;
                return GLib.SOURCE_REMOVE;
            }
            return GLib.SOURCE_CONTINUE;
        });
    }

    _stopClick() {
        if (this._clickTimeout)
            GLib.source_remove(this._clickTimeout);
        this._clickTimeout = 0;
        if (this._pointerPressed)
            this._pointer.notify_button(GLib.get_monotonic_time(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.RELEASED);
        this._pointerPressed = false;
    }

    _close(cancel = true) {
        this._stopClick();
        ++this._generation;
        if (this._overlay && cancel)
            this._call('Cancel', '(s)', [this._session ?? '']);
        for (const [object, id] of this._signals)
            object.disconnect(id);
        this._signals = [];
        if (this._timeout)
            GLib.source_remove(this._timeout);
        this._timeout = 0;
        if (this._grab)
            Main.popModal(this._grab);
        this._grab = null;
        this._overlay?.destroy();
        this._overlay = null;
        this._session = null;
        this._window = null;
        this._hints = [];
    }

    disable() {
        this._enabled = false;
        Main.wm.removeKeybinding('show-hints');
        Main.sessionMode.disconnect(this._modeSignal);
        this._close();
        this._settings = null;
        this._pointer = null;
    }
}
