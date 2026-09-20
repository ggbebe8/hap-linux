// Appended ONLY to the disposable staged extension by integration.sh.
// No test interface or input injection is shipped in the installed extension.
const testXML = `<node><interface name="io.github.haplinux.Test">
<method name="Prepare"><arg type="s" direction="in"/></method>
<method name="Key"><arg type="u" direction="in"/><arg type="b" direction="in"/></method>
<method name="State"><arg type="s" direction="out"/></method>
<method name="Capture"><arg type="s" direction="in"/></method>
<method name="Windows"><arg type="s" direction="out"/></method>
<method name="Resize"/>
</interface></node>`;
const productionEnable = HapExtension.prototype.enable;
const productionDisable = HapExtension.prototype.disable;
HapExtension.prototype.enable = function () {
    productionEnable.call(this);
    const device = global.stage.context.get_backend().get_default_seat()
        .create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
    this._testDriver = Gio.DBusExportedObject.wrapJSObject(testXML, {
        Windows: () => JSON.stringify(global.get_window_actors().map(a => ({title: a.meta_window.get_title(), pid: a.meta_window.get_pid()}))),
        Resize: () => {
            const win = global.display.focus_window;
            win.unmaximize();
            win.move_resize_frame(true, 180, 90, 920, 560);
        },
        CaptureAsync: async ([path], invocation) => {
            const stream = Gio.File.new_for_path(path).replace(null, false, Gio.FileCreateFlags.NONE, null);
            await new Shell.Screenshot().screenshot(true, stream);
            stream.close(null);
            invocation.return_value(null);
        },
        Prepare: title => {
            Main.overview.hide();
            const win = global.get_window_actors().map(actor => actor.meta_window)
                .find(win => win.get_title() === title);
            win?.activate(global.get_current_time());
        },
        Key: (key, pressed) => device.notify_keyval(GLib.get_monotonic_time(), key,
            pressed ? Clutter.KeyState.PRESSED : Clutter.KeyState.RELEASED),
        State: () => JSON.stringify({overlay: Boolean(this._overlay),
            grab: Boolean(this._grab), session: this._session,
            focus: global.display.focus_window?.get_title(),
            appId: global.display.focus_window?.get_gtk_application_id(),
            pointer: global.get_pointer(),
            notifications: Main.messageTray.getSources().flatMap(source => source.notifications.map(n => n.body)),
            hints: this._hints?.map(h => ({label: h.label, name: h.name,
                pointer: h.pointer, visible: h.actor.visible, x: h.actor.x, y: h.actor.y})),
            prefix: this._prefix}),
    });
    this._testDriver.export(Gio.DBus.session, '/io/github/haplinux/Test');
};
HapExtension.prototype.disable = function () {
    this._testDriver?.unexport();
    this._testDriver = null;
    productionDisable.call(this);
};
