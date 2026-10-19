import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Keyboard from 'resource:///org/gnome/shell/ui/keyboard.js';
import * as InputSources from 'resource:///org/gnome/shell/ui/status/keyboard.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// GNOME's Key constructor parses this field as a hexadecimal string.
const HANGUL_KEYVAL = '0xff31';
const KEY_WIDTH = 1.5;

function addHangulKey(keys) {
    const space = keys.find(key => key.strings?.[0] === ' ');
    const menuIndex = keys.findIndex(key => key.action === 'languageMenu');
    if (!space || menuIndex < 0 || (space.width ?? 1) < KEY_WIDTH + 1)
        return keys;

    const result = keys.map(key => ({...key, ...(key.strings ? {strings: [...key.strings]} : {})}));
    result[keys.indexOf(space)].width -= KEY_WIDTH;
    result.splice(menuIndex, 0, {label: '한/영', keyval: HANGUL_KEYVAL, width: KEY_WIDTH});
    return result;
}

export default class TouchKeyboardHangulKey extends Extension {
    enable() {
        this._injections = new InjectionManager();
        this._injections.overrideMethod(Keyboard.Keyboard.prototype, '_addRowKeys', original => {
            return function (keys, layout, emojiVisible) {
                const current = InputSources.getInputSourceManager().currentSource;
                const row = current?.id === 'hangul' ? addHangulKey(keys) : keys;
                return original.call(this, row, layout, emojiVisible);
            };
        });
        this._refreshExistingKeyboard();
    }

    disable() {
        this._injections?.clear();
        this._injections = null;
        this._refreshExistingKeyboard();
    }

    _refreshExistingKeyboard() {
        const keyboard = Main.keyboard?._keyboard;
        const source = InputSources.getInputSourceManager().currentSource;
        if (keyboard?._layers && source && (source.id !== 'hangul' || source.properties))
            keyboard._updateKeys();
    }
}
