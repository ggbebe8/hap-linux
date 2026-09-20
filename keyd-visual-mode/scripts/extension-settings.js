import Gio from 'gi://Gio';

// Preserve the user's other extensions, including the global enable/disable switch.
const uuid = 'keyd-visual-mode@local';
const settings = new Gio.Settings({schema_id: 'org.gnome.shell'});
const enable = ARGV[0] === 'enable';
if (!['enable', 'disable'].includes(ARGV[0]))
    throw new Error('Expected enable or disable');
for (const key of ['enabled-extensions', 'disabled-extensions']) {
    const values = settings.get_strv(key).filter(value => value !== uuid);
    if (enable && key === 'enabled-extensions')
        values.push(uuid);
    if (!settings.set_strv(key, values))
        throw new Error(`설정을 저장할 수 없습니다: ${key}`);
}
Gio.Settings.sync();
if (enable && settings.get_boolean('disable-user-extensions'))
    print('주의: GNOME 확장 전체가 꺼져 있습니다. 확장 앱에서 전체 스위치를 켜세요.');
