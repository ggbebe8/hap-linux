import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const INTERFACE = `<node>
  <interface name="org.gnome.Shell.Extensions.Touchgesture">
    <method name="Show">
      <arg type="s" name="title" direction="in"/>
      <arg type="s" name="body" direction="in"/>
      <arg type="u" name="duration_ms" direction="in"/>
    </method>
    <method name="Hide"/>
  </interface>
</node>`;
const PATH = '/org/gnome/Shell/Extensions/Touchgesture';

export default class TouchgestureOverlay extends Extension {
    enable() {
        this._timeout = 0;
        this._owner = null;
        this._ownerWatch = 0;
        this._card = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'touchgesture-card',
            reactive: false,
            can_focus: false,
            track_hover: false,
            visible: false,
        });
        this._arrows = new St.Label({style_class: 'touchgesture-arrows', reactive: false});
        this._title = new St.Label({style_class: 'touchgesture-title', reactive: false});
        for (const label of [this._arrows, this._title]) {
            label.x_align = Clutter.ActorAlign.CENTER;
            label.y_align = Clutter.ActorAlign.CENTER;
            this._card.add_child(label);
        }
        // No input region, keyboard focus, modal grab, or notification banner.
        Main.layoutManager.addChrome(this._card, {
            affectsStruts: false,
            trackFullscreen: false,
        });
        this._monitorsChanged = Main.layoutManager.connect('monitors-changed', () => this._hide());
        this._sessionChanged = Main.sessionMode.connect('updated', () => this._hide());
        this._dbus = Gio.DBusExportedObject.wrapJSObject(INTERFACE, this);
        this._dbus.export(Gio.DBus.session, PATH);
    }

    ShowAsync([title, body, duration], invocation) {
        try {
            const sender = invocation.get_sender();
            if (this._owner !== sender) {
                this._clearOwner();
                this._owner = sender;
                this._ownerWatch = Gio.bus_watch_name_on_connection(
                    Gio.DBus.session, sender, Gio.BusNameWatcherFlags.NONE, null,
                    () => this._hide());
            }
            this._show(title, body, duration);
            invocation.return_value(null);
        } catch (error) {
            invocation.return_dbus_error('org.gnome.Shell.Extensions.Touchgesture.Error', error.message);
        }
    }

    HideAsync(_params, invocation) {
        if (this._owner === invocation.get_sender())
            this._hide();
        invocation.return_value(null);
    }

    _show(title, body, duration) {
        this._hide(false);
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter || duration === 0)
            return;
        const monitorIndex = global.display.focus_window?.get_monitor();
        const monitor = Main.layoutManager.monitors[monitorIndex] ?? Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;
        const firstLine = body.split('\n')[0];
        const arrows = firstLine.match(/[↑↓←→]+/u)?.[0] ?? '✓';
        this._arrows.text = [...arrows].join(' ');
        this._title.text = title
            .replace(/^(손을 떼면|미리보기):\s*/u, '')
            .replace(/\s*· 실행 안 함$/u, '')
            .slice(0, 160);
        this._card.show();
        this._card.ensure_style();
        this._card.width = -1;
        const [, naturalWidth] = this._card.get_preferred_width(-1);
        this._card.width = Math.min(naturalWidth, monitor.width - 32);
        const [, height] = this._card.get_preferred_height(this._card.width);
        this._card.set_position(Math.round(monitor.x + (monitor.width - this._card.width) / 2),
            Math.round(monitor.y + (monitor.height - height) / 2));
        this._timeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, Math.min(duration, 10000), () => {
            this._timeout = 0;
            this._hide();
            return GLib.SOURCE_REMOVE;
        });
    }

    _clearOwner() {
        if (this._ownerWatch) {
            Gio.bus_unwatch_name(this._ownerWatch);
            this._ownerWatch = 0;
        }
        this._owner = null;
    }

    _hide(clearOwner = true) {
        if (this._timeout) {
            GLib.source_remove(this._timeout);
            this._timeout = 0;
        }
        this._card?.hide();
        if (clearOwner)
            this._clearOwner();
    }

    disable() {
        this._hide();
        this._dbus?.unexport();
        this._dbus = null;
        if (this._monitorsChanged)
            Main.layoutManager.disconnect(this._monitorsChanged);
        if (this._sessionChanged)
            Main.sessionMode.disconnect(this._sessionChanged);
        this._monitorsChanged = this._sessionChanged = 0;
        if (this._card) {
            Main.layoutManager.removeChrome(this._card);
            this._card.destroy();
            this._card = null;
        }
    }
}
