import St from 'gi://St';
import Clutter from 'gi://Clutter';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {LayerMonitor} from './monitor.js';

const ACTIVE_CLASS = 'keyd-visual-mode-active';

export default class KeydVisualMode extends Extension {
    enable() {
        this._indicator = new PanelMenu.Button(0.0, 'Keyd Visual Mode');
        this._label = new St.Label({y_align: Clutter.ActorAlign.CENTER});
        this._indicator.add_child(this._label);
        this._status = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._indicator.menu.addMenuItem(this._status);
        this._indicator.menu.addAction('keyd 다시 연결', () => this._monitor.start());
        Main.panel.addToStatusArea(this.uuid, this._indicator);
        this._monitor = new LayerMonitor(state => this._setState(state));
        this._monitor.start();
    }

    _setState(state) {
        const active = state === 'on';
        if (active)
            Main.panel.add_style_class_name(ACTIVE_CLASS);
        else
            Main.panel.remove_style_class_name(ACTIVE_CLASS);
        this._indicator.visible = state !== 'off';
        this._label.text = active ? 'V' : '!';
        this._label.style_class = active ? 'keyd-visual-mode-label' : 'keyd-visual-mode-error';
        this._indicator.accessible_name = active ? 'keyd 고정 레이어 활성화' : 'keyd 연결 오류';
        this._status.label.text = active ? 'caps_locked 활성화' : 'keyd 연결 끊김 · 상태 확인 불가';
    }

    disable() {
        this._monitor?.stop();
        this._monitor = null;
        Main.panel.remove_style_class_name(ACTIVE_CLASS);
        this._indicator?.destroy();
        this._indicator = null;
        this._label = null;
        this._status = null;
    }
}
