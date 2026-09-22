import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Grid, KEYS} from './grid.js';

const MODIFIERS = Clutter.ModifierType.CONTROL_MASK | Clutter.ModifierType.MOD1_MASK |
    Clutter.ModifierType.SUPER_MASK | Clutter.ModifierType.SHIFT_MASK;
const PHYSICAL = {24: 'Q', 25: 'W', 26: 'E', 38: 'A', 39: 'S', 40: 'D', 52: 'Z', 53: 'X', 54: 'C', 27: 'R', 43: 'H'};

export default class GridClick extends Extension {
    enable() {
        this._pointer = global.stage.context.get_backend().get_default_seat()
            .create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
        this._seat = global.stage.context.get_backend().get_default_seat();
        this._cursorTracker = global.backend.get_cursor_tracker();
        this._settings = this.getSettings();
        this._signals = [
            [this._cursorTracker, this._cursorTracker.connect('position-invalidated', () => {
                if (!this._cursorHidden) return;
                const [x, y] = global.get_pointer();
                if (x !== this._hiddenPoint[0] || y !== this._hiddenPoint[1])
                    this._restoreCursor();
            })],
            [Main.sessionMode, Main.sessionMode.connect('updated', () => this._close())],
            [Main.layoutManager, Main.layoutManager.connect('monitors-changed', () => this._close())],
            [Main.overview, Main.overview.connect('showing', () => this._close())],
        ];
        Main.wm.addKeybinding('show-grid', this._settings, Meta.KeyBindingFlags.IGNORE_AUTOREPEAT,
            Shell.ActionMode.NORMAL, () => this._toggle());
    }

    _toggle() {
        if (this._overlay) { this._close(); return; }
        this._stopClick();
        if (Main.sessionMode.isLocked || Main.overview.visible) return;
        try {
            const monitors = Main.layoutManager.monitors;
            const [px, py] = global.get_pointer();
            const index = global.display.focus_window?.get_monitor() ??
                Math.max(0, monitors.findIndex(m => px >= m.x && py >= m.y && px < m.x + m.width && py < m.y + m.height));
            this._grid = new Grid(monitors, index);
            this._helpVisible = false;
            this._overlay = new St.Widget({reactive: true, can_focus: true,
                layout_manager: new Clutter.FixedLayout(), width: global.stage.width, height: global.stage.height});
            Main.layoutManager.addTopChrome(this._overlay, {trackFullscreen: false});
            this._overlay.connect('key-press-event', (_actor, event) => this._key(event));
            this._overlay.connect('button-press-event', () => { this._close(); return Clutter.EVENT_STOP; });
            this._grab = Main.pushModal(this._overlay, {actionMode: Shell.ActionMode.POPUP});
            if (this._grab.is_revoked()) throw new Error('키보드를 확보하지 못했습니다. 열린 메뉴를 닫고 다시 시도하세요.');
            this._render();
        } catch (error) {
            this._close();
            Main.notify('Grid Click', error.message);
        }
    }

    _key(event) {
        const key = event.get_key_symbol();
        if (key === Clutter.KEY_Escape) { this._close(); return Clutter.EVENT_STOP; }
        // Ignore shortcut modifiers while the opening shortcut is being released.
        if (event.get_state() & (MODIFIERS & ~Clutter.ModifierType.SHIFT_MASK)) return Clutter.EVENT_STOP;
        if (key === Clutter.KEY_question) {
            this._helpVisible = !this._helpVisible;
            this._render();
            return Clutter.EVENT_STOP;
        }
        const unicode = Clutter.keysym_to_unicode(key);
        const text = unicode ? String.fromCodePoint(unicode).toUpperCase() : '';
        const letter = /^[A-Z]$/.test(text) ? text : PHYSICAL[event.get_key_code()];
        if (key === Clutter.KEY_Return || key === Clutter.KEY_KP_Enter) this._commit(1, 1);
        else if (key === Clutter.KEY_space) this._commit(1, 2);
        else if (letter === 'R') this._commit(3, 1);
        else if (letter === 'H') this._commit(null, 0);
        else {
            if (key === Clutter.KEY_BackSpace) this._grid.back();
            else if (key === Clutter.KEY_Tab || key === Clutter.KEY_ISO_Left_Tab) this._grid.nextMonitor();
            else if (key === Clutter.KEY_Home) this._grid.reset();
            else if (KEYS.includes(letter ?? '') && letter) this._grid.select(letter);
            else {
                const step = event.get_state() & Clutter.ModifierType.SHIFT_MASK ? 10 : 1;
                const delta = { [Clutter.KEY_Left]: [-step, 0], [Clutter.KEY_Right]: [step, 0],
                    [Clutter.KEY_Up]: [0, -step], [Clutter.KEY_Down]: [0, step] }[key];
                if (!delta) return Clutter.EVENT_STOP;
                this._grid.nudge(...delta);
            }
            this._render();
        }
        return Clutter.EVENT_STOP;
    }

    _render() {
        this._overlay.destroy_all_children();
        for (const cell of this._grid.cells()) {
            const box = new St.Widget({style_class: 'grid-click-cell', x: cell.x, y: cell.y,
                width: cell.width, height: cell.height});
            this._overlay.add_child(box);
            if (cell.width >= 28 && cell.height >= 28) {
                const label = new St.Label({style_class: 'grid-click-letter', text: cell.key});
                label.set_position(cell.x + cell.width / 2 - 13, cell.y + cell.height / 2 - 14);
                this._overlay.add_child(label);
            }
        }
        const [x, y] = this._grid.point;
        for (const [w, h] of [[21, 3], [3, 21]])
            this._overlay.add_child(new St.Widget({style_class: 'grid-click-cross',
                x: x - w / 2, y: y - h / 2, width: w, height: h}));
        if (!this._helpVisible) return;
        const m = this._grid.monitors[this._grid.index];
        const area = this._grid.area;
        const status = new St.Label({style_class: 'grid-click-status', text:
            `Grid Click · 화면 ${this._grid.index + 1}/${this._grid.monitors.length} · ${Math.round(area.width)}×${Math.round(area.height)} · (${x}, ${y})\n` +
            'QWE / ASD / ZXC 좁히기 · 방향키 미세 조정 · Backspace 되돌리기\n' +
            'Enter 클릭 · Space 더블클릭 · R 오른쪽 · H 호버 · Tab 화면 · Home 처음 · Esc 취소 · ? 도움말 닫기'});
        status.set_position(m.x + 12, m.y + 36);
        this._overlay.add_child(status);
    }

    _commit(button, clicks) {
        const [x, y] = this._grid.point;
        this._close();
        // Wait for modifiers and the modal grab to be released before input.
        let step = -1, attempts = 0;
        this._clickTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, () => {
            if (Main.sessionMode.isLocked || Main.overview.visible) {
                this._clickTimer = 0; this._stopClick(); return GLib.SOURCE_REMOVE;
            }
            if (step === -1) {
                if (global.get_pointer()[2] & MODIFIERS) {
                    if (++attempts < 20) return GLib.SOURCE_CONTINUE;
                    this._clickTimer = 0;
                    Main.notify('Grid Click', '보조키를 놓은 뒤 다시 선택하세요.');
                    return GLib.SOURCE_REMOVE;
                }
                this._pointer.notify_absolute_motion(GLib.get_monotonic_time(), x, y);
                if (clicks === 0) { this._clickTimer = 0; this._hideCursorAfterInput(x, y); return GLib.SOURCE_REMOVE; }
                step = 0;
                return GLib.SOURCE_CONTINUE;
            }
            const [px, py] = global.get_pointer();
            if (Math.abs(px - x) > 1 || Math.abs(py - y) > 1 || global.get_pointer()[2] & MODIFIERS) {
                this._clickTimer = 0; this._stopClick(); return GLib.SOURCE_REMOVE;
            }
            this._heldButton = step % 2 === 0 ? button : null;
            this._pointer.notify_button(GLib.get_monotonic_time(), button,
                this._heldButton ? Clutter.ButtonState.PRESSED : Clutter.ButtonState.RELEASED);
            if (++step === clicks * 2) { this._clickTimer = 0; this._hideCursorAfterInput(x, y); return GLib.SOURCE_REMOVE; }
            return GLib.SOURCE_CONTINUE;
        });
    }

    _hideCursorAfterInput(x, y) {
        // Let our queued motion/button events reach the application first.
        this._hideTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, () => {
            this._hideTimer = 0;
            const [px, py] = global.get_pointer();
            if (px !== x || py !== y || Main.sessionMode.isLocked || Main.overview.visible)
                return GLib.SOURCE_REMOVE;
            // Visibility inhibition normally drops Wayland pointer focus. Keep
            // focus so hover effects and tooltips survive while only the image hides.
            this._seat.inhibit_unfocus();
            this._cursorTracker.inhibit_cursor_visibility();
            this._hiddenPoint = [x, y];
            this._cursorHidden = true;
            return GLib.SOURCE_REMOVE;
        });
    }

    _restoreCursor() {
        if (this._hideTimer) GLib.source_remove(this._hideTimer);
        this._hideTimer = 0;
        if (!this._cursorHidden) return;
        this._cursorHidden = false;
        this._cursorTracker.uninhibit_cursor_visibility();
        this._seat.uninhibit_unfocus();
    }

    _stopClick() {
        if (this._clickTimer) GLib.source_remove(this._clickTimer);
        this._clickTimer = 0;
        if (this._heldButton)
            this._pointer.notify_button(GLib.get_monotonic_time(), this._heldButton, Clutter.ButtonState.RELEASED);
        this._heldButton = null;
    }

    _close() {
        this._restoreCursor();
        this._stopClick();
        if (this._grab) Main.popModal(this._grab);
        this._grab = null;
        this._overlay?.destroy();
        this._overlay = null;
        this._grid = null;
    }

    disable() {
        Main.wm.removeKeybinding('show-grid');
        this._close();
        for (const [object, id] of this._signals) object.disconnect(id);
        this._signals = [];
        this._pointer = null;
        this._cursorTracker = null;
        this._seat = null;
        this._settings = null;
    }
}
