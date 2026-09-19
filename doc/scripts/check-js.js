const {GLib} = imports.gi;
const decoder = new TextDecoder();
const [ok, bytes] = GLib.file_get_contents(ARGV[0]);
if (!ok) throw new Error('Cannot read extension');
Reflect.parse(decoder.decode(bytes), {target: 'module'});
print('GJS module syntax OK');
