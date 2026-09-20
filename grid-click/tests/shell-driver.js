// Test-only interface, appended to the isolated staged copy only.
import Gio from 'gi://Gio';
const testXML = `<node><interface name="io.github.gridclick.Test">
<method name="Prepare"/>
<method name="Key"><arg type="u" direction="in"/><arg type="b" direction="in"/></method>
<method name="State"><arg type="s" direction="out"/></method>
<method name="Capture"><arg type="s" direction="in"/></method>
</interface></node>`;
const originalEnable = GridClick.prototype.enable;
const originalDisable = GridClick.prototype.disable;
GridClick.prototype.enable = function () {
    originalEnable.call(this);
    const keyboard = global.stage.context.get_backend().get_default_seat()
        .create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
    this._testDriver = Gio.DBusExportedObject.wrapJSObject(testXML, {
        Prepare: () => {
            Main.overview.hide();
            global.get_window_actors().find(a => a.meta_window.get_title() === 'Grid Click Fixture')?.meta_window.activate(global.get_current_time());
        },
        Key: (key, pressed) => keyboard.notify_keyval(GLib.get_monotonic_time(), key,
            pressed ? Clutter.KeyState.PRESSED : Clutter.KeyState.RELEASED),
        State: () => {
            const win = global.get_window_actors().find(a => a.meta_window.get_title() === 'Grid Click Fixture')?.meta_window;
            const r = win?.get_frame_rect();
            return JSON.stringify({overlay: Boolean(this._overlay), grab: Boolean(this._grab),
                grid: this._grid ? {area: this._grid.area, point: this._grid.point,
                    index: this._grid.index, monitors: this._grid.monitors, cells: this._grid.cells(), depth: this._grid.history.length} : null,
                frame: r ? {x: r.x, y: r.y, width: r.width, height: r.height} : null,
                pointer: global.get_pointer(), clicking: Boolean(this._clickTimer)});
        },
        CaptureAsync: async ([path], invocation) => {
            const stream = Gio.File.new_for_path(path).replace(null, false, Gio.FileCreateFlags.NONE, null);
            await new Shell.Screenshot().screenshot(true, stream);
            stream.close(null);
            invocation.return_value(null);
        },
    });
    this._testDriver.export(Gio.DBus.session, '/io/github/gridclick/Test');
};
GridClick.prototype.disable = function () {
    this._testDriver?.unexport();
    this._testDriver = null;
    originalDisable.call(this);
};
