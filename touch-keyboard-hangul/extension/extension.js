import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Keyboard from 'resource:///org/gnome/shell/ui/keyboard.js';
import * as InputSources from 'resource:///org/gnome/shell/ui/status/keyboard.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// GNOME's Key constructor parses this field as a hexadecimal string.
const HANGUL_KEYVAL = '0xff31';
const KEY_WIDTH = 1.5;

const HANGUL_MAP = {
    // Default (소문자 / 두벌식 기본 자모)
    'q': 'ㅂ', 'w': 'ㅈ', 'e': 'ㄷ', 'r': 'ㄱ', 't': 'ㅅ',
    'y': 'ㅛ', 'u': 'ㅕ', 'i': 'ㅑ', 'o': 'ㅐ', 'p': 'ㅔ',
    'a': 'ㅁ', 's': 'ㄴ', 'd': 'ㅇ', 'f': 'ㄹ', 'g': 'ㅎ',
    'h': 'ㅗ', 'j': 'ㅓ', 'k': 'ㅏ', 'l': 'ㅣ',
    'z': 'ㅋ', 'x': 'ㅌ', 'c': 'ㅊ', 'v': 'ㅍ', 'b': 'ㅠ',
    'n': 'ㅜ', 'm': 'ㅡ',

    // Shift (대문자 / 두벌식 쌍자음 및 복모음)
    'Q': 'ㅃ', 'W': 'ㅉ', 'E': 'ㄸ', 'R': 'ㄲ', 'T': 'ㅆ',
    'Y': 'ㅛ', 'U': 'ㅕ', 'I': 'ㅑ', 'O': 'ㅒ', 'P': 'ㅖ',
    'A': 'ㅁ', 'S': 'ㄴ', 'D': 'ㅇ', 'F': 'ㄹ', 'G': 'ㅎ',
    'H': 'ㅗ', 'J': 'ㅓ', 'K': 'ㅏ', 'L': 'ㅣ',
    'Z': 'ㅋ', 'X': 'ㅌ', 'C': 'ㅊ', 'V': 'ㅍ', 'B': 'ㅠ',
    'N': 'ㅜ', 'M': 'ㅡ',
};

function isHangulMode(keyboard, currentSource) {
    if (currentSource?.id !== 'hangul')
        return false;

    // GNOME Shell's KeyboardController.getCurrentGroup() returns 'us'
    // when IBus Hangul is in English mode, and the XKB id ('kr') when in Hangul mode.
    try {
        const group = keyboard?._keyboardController?.getCurrentGroup?.();
        if (typeof group === 'string')
            return group !== 'us';
    } catch {
        // Fallback to checking properties directly
    }

    if (!currentSource.properties)
        return true;

    try {
        let prop;
        for (let i = 0; (prop = currentSource.properties.get(i)) !== null; ++i) {
            if (prop.get_key() === 'InputMode')
                return prop.get_state() === 1; // 1: IBus.PropState.CHECKED
        }
    } catch {
        // Fallback
    }

    return true;
}

function processRowKeys(keys, isHangulSource, inHangulMode) {
    const result = keys.map(key => {
        const copy = {...key, ...(key.strings ? {strings: [...key.strings]} : {})};

        if (inHangulMode && copy.strings && copy.strings.length > 0) {
            const firstChar = copy.strings[0];
            const hangulChar = HANGUL_MAP[firstChar];
            if (hangulChar && !copy.action && !copy.keyval) {
                copy.label = hangulChar;
                copy.strings = [firstChar];
            }
        }

        return copy;
    });

    if (!isHangulSource)
        return result;

    const spaceIndex = result.findIndex(key => key.strings?.[0] === ' ');
    const menuIndex = result.findIndex(key => key.action === 'languageMenu');

    if (spaceIndex < 0 || menuIndex < 0)
        return result;

    const space = result[spaceIndex];
    if ((space.width ?? 1) < KEY_WIDTH + 1)
        return result;

    space.width -= KEY_WIDTH;
    result.splice(menuIndex, 0, {
        label: '한/영',
        keyval: HANGUL_KEYVAL,
        width: KEY_WIDTH,
    });

    return result;
}

export default class TouchKeyboardHangulKey extends Extension {
    enable() {
        this._injections = new InjectionManager();
        this._injections.overrideMethod(Keyboard.Keyboard.prototype, '_addRowKeys', original => {
            return function (keys, layout, emojiVisible) {
                const current = InputSources.getInputSourceManager().currentSource;
                const isHangulSource = current?.id === 'hangul';
                const inHangulMode = isHangulMode(this, current);

                const row = isHangulSource
                    ? processRowKeys(keys, isHangulSource, inHangulMode)
                    : keys;
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
