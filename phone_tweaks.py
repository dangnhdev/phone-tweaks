#!/usr/bin/env python3
"""Audit/plan Samsung qua ADB; chỉ ghi khi có --apply và authorization."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
PROFILES = {'s23-ultra': ('SM-S918B', 'wireless'), 'tab-s8': ('SM-X700', 'usb')}
SOURCES = {
    'samsungdebloat': 'https://github.com/itxjobe/samsungdebloat',
    'uad-ng': 'https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation',
}
CANDIDATES = {
    'com.facebook.system': ('Meta App Installer; chỉ chọn nếu không dùng tích hợp/cài đặt Meta của hãng.',
                            'community-configs/privacy-focused.txt'),
    'com.facebook.appmanager': ('Meta App Manager; mất cập nhật Meta qua dịch vụ OEM. Giữ nếu còn cần.',
                                'community-configs/privacy-focused.txt'),
    'com.samsung.android.rubin.app': ('Customization Service; mất cá nhân hóa và đề xuất theo hành vi.',
                                     '03-safe-system-apps.txt'),
    'com.samsung.android.mapsagent': ('Bỏ dịch vụ đề xuất ứng dụng Samsung và đối tác.',
                                     '03-safe-system-apps.txt'),
    'com.sec.android.app.chromecustomizations': ('Bỏ tùy biến Chrome của Samsung.',
                                               '03-safe-system-apps.txt'),
    'com.samsung.android.aremoji': ('Tắt tính năng AR Emoji của Samsung.',
                                   '01-safe-user-apps.txt'),
    'com.samsung.android.aremojieditor': ('Tắt trình chỉnh sửa AR Emoji.',
                                         '01-safe-user-apps.txt'),
}
STATES = {0: 'default-state', 1: 'enable', 2: 'disable', 3: 'disable-user', 4: 'disable-until-used'}
LABELS = {0: 'default', 1: 'enabled', 2: 'disabled', 3: 'disabled-user', 4: 'disabled-until-used'}


class SafetyError(Exception):
    pass


def run(argv, timeout=90):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # Không đưa transport/serial từ stderr của adb vào output công khai.
        raise SafetyError('Lệnh thất bại; dừng an toàn (exit %s).' % result.returncode)
    return result.stdout.replace('\r', '').strip()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, value):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def private_dir(profile, kind):
    base = ROOT / 'backups' / profile
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    return Path(tempfile.mkdtemp(prefix=kind + '-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'), dir=base))


def refresh():
    """Luôn fetch remote HEAD; đọc bằng git show, không chạy code upstream."""
    cache = ROOT / '.cache' / 'references'
    cache.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, url in SOURCES.items():
        repo = cache / name
        if not (repo / '.git').is_dir():
            run(['git', 'clone', '--no-checkout', '--depth', '1', url, str(repo)], 180)
        run(['git', '-C', str(repo), 'fetch', '--depth', '1', url, 'HEAD'], 180)
        commit = run(['git', '-C', str(repo), 'rev-parse', 'FETCH_HEAD'])
        manifest[name] = {'url': url, 'commit': commit, 'fetched_utc': utc()}
    save(cache / 'manifest.json', manifest)
    return manifest


def source_text(refs, name, path):
    return run(['git', '-C', str(ROOT / '.cache' / 'references' / name),
                'show', refs[name]['commit'] + ':' + path])


def evidence(refs, package):
    path = CANDIDATES[package][1]
    samsung = source_text(refs, 'samsungdebloat', path)
    uad_path = 'resources/assets/uad_lists.json'
    uad = json.loads(source_text(refs, 'uad-ng', uad_path))
    supported = any(line.strip() in (package, 'adb shell pm uninstall --user 0 ' + package)
                    for line in samsung.splitlines())
    if not supported or uad.get(package, {}).get('removal') != 'Recommended':
        raise SafetyError('Nguồn mới không còn hỗ trợ candidate ' + package)
    return {name: dict(refs[name], path=p) for name, p in
            [('samsungdebloat', path), ('uad-ng', uad_path)]}


class Device:
    def __init__(self, profile, serial):
        if not isinstance(serial, str) or not serial or not re.fullmatch(r'[A-Za-z0-9_.:\-]+', serial) or serial.startswith('-'):
            raise SafetyError('Cần --serial rõ ràng hoặc binding trong devices.local.json.')
        self.profile, self.serial = profile, serial
        self.model, transport = PROFILES[profile]
        listing = run(['adb', 'devices', '-l']).splitlines()
        rows = [line.split() for line in listing if line.split() and line.split()[0] == serial]
        if len(rows) != 1 or len(rows[0]) < 2 or rows[0][1] != 'device':
            raise SafetyError('Thiết bị offline/unauthorized/không xác định; dừng.')
        if transport == 'usb' and not any(x.startswith('usb:') for x in rows[0][2:]):
            raise SafetyError('Profile tab-s8 yêu cầu USB.')
        if transport == 'wireless' and not re.fullmatch(r'[A-Za-z0-9.\-]+:[0-9]+', serial):
            raise SafetyError('Profile s23-ultra yêu cầu endpoint host:port.')
        if self.shell('getprop', 'ro.product.model') != self.model:
            raise SafetyError('Model mismatch; dừng.')
        hardware = self.shell('getprop', 'ro.serialno')
        if not hardware or hardware.lower() in ('unknown', 'null'):
            raise SafetyError('Không đọc được hardware serial.')
        self.identity = {'profile': profile, 'model': self.model, 'hardware_serial': hardware}

    def shell(self, *args):
        out = run(['adb', '-s', self.serial, 'shell', *args])
        if args and args[0] == 'pm' and args[1] != 'list' and re.search(r'(?im)\b(error|failure|failed|exception|permission denial|not found)\b', out):
            raise SafetyError('ADB shell báo lỗi; dừng an toàn.')
        return out

    def validate(self):
        if Device(self.profile, self.serial).identity != self.identity:
            raise SafetyError('Device identity thay đổi; dừng.')

    def packages(self):
        out = self.shell('pm', 'list', 'packages', '--user', '0')
        if not out or any(not re.fullmatch(r'package:[A-Za-z0-9_.]+', x) for x in out.splitlines()):
            raise SafetyError('Không đọc được installed packages user 0.')
        return {x[8:] for x in out.splitlines()}

    def state(self, package):
        out = self.shell('dumpsys', 'package', package)
        active = out.split('Hidden system packages:', 1)[0]
        blocks = re.findall(r'^[ \t]*Package \[([^\]]+)\][^\n]*\n(.*?)(?=^[ \t]*Package \[|\Z)',
                            active, re.M | re.S)
        matches = [body for name, body in blocks if name == package]
        if len(matches) != 1:
            raise SafetyError('Không xác định active package ' + package)
        users = re.findall(r'^[ \t]*User 0:([^\n]*\binstalled=(?:true|false)\b[^\n]*)',
                           matches[0], re.M)
        if len(users) != 1 or not re.search(r'\binstalled=true\b', users[0]):
            raise SafetyError('Không xác định package/user 0 ' + package)
        found = re.search(r'\benabled=([0-4])\b', users[0])
        if not found:
            raise SafetyError('Không đọc được trạng thái gốc ' + package)
        return int(found[1])

    def change(self, package, state):
        self.validate()
        out = self.shell('pm', STATES[state], '--user', '0', package)
        expected = LABELS[state]
        if not re.fullmatch(r'Package ' + re.escape(package) + r' new state: ' + expected, out):
            raise SafetyError('pm không xác nhận thành công ' + package)
        if self.state(package) != state:
            raise SafetyError('Read-back state mismatch ' + package)


def make_plan(device, refs, selected):
    if len(selected) != len(set(selected)):
        raise SafetyError('Package bị chọn lặp; dừng trước mọi thay đổi.')
    installed = device.packages()
    rows = []
    for package in selected or CANDIDATES:
        if package not in CANDIDATES:
            raise SafetyError('Package ngoài allowlist ' + package)
        rows.append({'package': package, 'reason': CANDIDATES[package][0],
                     'present': package in installed,
                     'original': device.state(package) if package in installed else None,
                     'evidence': evidence(refs, package)})
    return {'created_utc': utc(), 'identity': device.identity, 'references': refs, 'packages': rows}


def debloat(device, refs, selected, apply, authorization, reviewed=None):
    if apply and (not selected or not authorization.strip()):
        raise SafetyError('--apply cần --package cụ thể và --authorization ghi quyết định riêng của user.')
    plan = make_plan(device, refs, selected)
    if apply:
        if not reviewed:
            raise SafetyError('--apply cần --journal của plan đã review.')
        approved = read_record(reviewed)
        if approved.get('kind') != 'plan' or approved.get('identity') != device.identity:
            raise SafetyError('Plan không thuộc cùng hardware serial/model/profile.')
        def stable_rows(rows):
            return [dict(row, evidence={name: {key: value for key, value in source.items()
                                              if key != 'fetched_utc'}
                                        for name, source in row['evidence'].items()})
                    for row in rows]
        if (stable_rows(approved['packages']) != stable_rows(plan['packages'])
                or {k: v['commit'] for k, v in approved['references'].items()}
                != {k: v['commit'] for k, v in refs.items()}):
            raise SafetyError('Package, trạng thái hoặc nguồn đã đổi; review plan mới.')
    folder = private_dir(device.profile, 'debloat' if apply else 'plan')
    journal = folder / 'journal.json'
    plan.update(kind='debloat' if apply else 'plan', entries=[])
    if apply:
        plan['authorization'] = authorization
    save(journal, plan)
    print('Dữ liệu riêng tư:', journal.relative_to(ROOT))
    for row in plan['packages']:
        print(row['package'], 'có mặt' if row['present'] else 'không cài', row['reason'])
        if not apply or not row['present'] or row['original'] in (2, 3, 4):
            continue
        device.validate()
        if device.state(row['package']) != row['original']:
            raise SafetyError('Trạng thái thay đổi từ lúc plan; tạo plan mới.')
        entry = {'package': row['package'], 'original': row['original'], 'status': 'pending'}
        plan['entries'].append(entry)
        plan['authorization'] = authorization
        save(journal, plan)  # Write-ahead để rollback được cả khi adb mất kết nối sau dispatch.
        try:
            device.change(row['package'], 3)
        except Exception:
            entry['status'] = 'uncertain'
            save(journal, plan)
            raise
        entry['status'] = 'disabled'
        save(journal, plan)
    return journal


def read_record(journal):
    journal = Path(journal).resolve()
    if not journal.is_relative_to((ROOT / 'backups').resolve()):
        raise SafetyError('Chỉ nhận journal rõ ràng trong backups/.')
    data = json.loads(journal.read_text())
    if (not isinstance(data, dict) or not isinstance(data.get('identity'), dict)
            or not isinstance(data.get('references'), dict)
            or not isinstance(data.get('packages'), list)
            or not isinstance(data.get('entries'), list)):
        raise SafetyError('Journal thiếu cấu trúc bắt buộc.')
    if any(not isinstance(source, dict) or not isinstance(source.get('commit'), str)
           for source in data['references'].values()):
        raise SafetyError('References trong journal không hợp lệ.')
    for row in data['packages']:
        if (not isinstance(row, dict) or not isinstance(row.get('evidence'), dict)
                or any(not isinstance(source, dict) for source in row['evidence'].values())):
            raise SafetyError('Package evidence trong journal không hợp lệ.')
    for entry in data['entries']:
        if not isinstance(entry, dict) or not isinstance(entry.get('package'), str):
            raise SafetyError('Entry trong journal không hợp lệ.')
    return data


def rollback(device, journal, apply, authorization, selected=()):
    data = read_record(journal)
    device.validate()
    if data.get('kind') != 'debloat' or data.get('identity') != device.identity:
        raise SafetyError('Journal không thuộc cùng hardware serial/model/profile.')
    entries = data.get('entries', [])
    if len({e.get('package') for e in entries}) != len(entries):
        raise SafetyError('Journal trùng package.')
    for entry in entries:
        if (entry.get('package') not in CANDIDATES or type(entry.get('original')) is not int
                or entry['original'] not in STATES or entry.get('status') not in
                ('pending', 'uncertain', 'disabled', 'restored')):
            raise SafetyError('Journal không hợp lệ.')
    if selected:
        if len(selected) != len(set(selected)) or set(selected) - {e['package'] for e in entries}:
            raise SafetyError('Package rollback không có trong journal hoặc bị chọn lặp.')
        entries = [e for e in entries if e['package'] in selected]
    if apply and not authorization.strip():
        raise SafetyError('Rollback --apply cần --authorization riêng.')
    for entry in entries:
        device.validate()
        current = device.state(entry['package'])
        device.validate()
        if ((entry['status'] == 'restored' and current != entry['original'])
                or current not in (3, entry['original'])):
            raise SafetyError('State đã bị thay đổi bên ngoài; chọn riêng package còn hợp lệ bằng --package.')
    for entry in reversed(entries):
        package, original = entry['package'], entry['original']
        device.validate()
        current = device.state(package)
        device.validate()
        if (entry['status'] == 'restored' and current != original) or current not in (3, original):
            raise SafetyError('State đã bị thay đổi bên ngoài; dừng ' + package)
        print('Đã khôi phục' if entry['status'] == 'restored' else 'Khôi phục', package, 'về', LABELS[original])
        if apply and current != original:
            device.change(package, original)
        if apply:
            device.validate()
            entry['status'] = 'restored'
            data['rollback_authorization'] = authorization
            save(journal, data)


def audit(device):
    folder = private_dir(device.profile, 'audit')
    save(folder / 'identity.json', dict(device.identity, captured_utc=utc()))
    commands = {
        'getprop-full': ('getprop',), 'packages-all': ('pm', 'list', 'packages', '--user', '0'),
        'packages-disabled': ('pm', 'list', 'packages', '-d', '--user', '0'),
        'dumpsys-package': ('dumpsys', 'package'), 'diskstats': ('dumpsys', 'diskstats'),
        'usagestats-plain': ('dumpsys', 'usagestats'), 'meminfo': ('cat', '/proc/meminfo'),
        'battery': ('dumpsys', 'battery'), 'df': ('df', '-h'),
    }
    errors = []
    for name, args in commands.items():
        try:
            device.validate()
            output = device.shell(*args)
            (folder / (name + '.txt')).write_text(output + '\n')
        except (SafetyError, OSError, ValueError, subprocess.TimeoutExpired):
            errors.append(name)
    save(folder / 'audit-status.json', {'complete': not errors, 'failed': errors})
    print('Audit riêng tư:', folder.relative_to(ROOT))
    if errors:
        raise SafetyError('Audit chưa đầy đủ: ' + ', '.join(errors))


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'audit', 'plan', 'debloat', 'rollback', 'refresh'])
    parser.add_argument('--device', choices=PROFILES)
    parser.add_argument('--serial', help='Transport rõ ràng; ưu tiên hơn binding local.')
    parser.add_argument('--package', action='append', default=[], help='Chọn từng candidate, lặp lại được.')
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--apply', action='store_true', help='Ghi thiết bị, chỉ sau authorization riêng.')
    parser.add_argument('--authorization', default='', help='Ghi lại quyết định cụ thể user đã cho phép.')
    args = parser.parse_args(argv)
    allowed = {
        'status': {'device', 'serial'}, 'audit': {'device', 'serial'},
        'plan': {'device', 'serial', 'package'}, 'refresh': set(),
        'debloat': {'device', 'serial', 'package', 'journal', 'apply', 'authorization'},
        'rollback': {'device', 'serial', 'package', 'journal', 'apply', 'authorization'},
    }
    for flag, value in vars(args).items():
        if flag != 'command' and value and flag not in allowed[args.command]:
            parser.error('--' + flag + ' không áp dụng cho ' + args.command)
    if args.command == 'debloat' and args.journal and not args.apply:
        parser.error('--journal của debloat chỉ áp dụng cùng --apply')
    if args.authorization and not args.apply:
        parser.error('--authorization cần --apply')
    if args.command == 'refresh':
        print(json.dumps(refresh(), indent=2))
        return
    if not args.device:
        parser.error('cần --device')
    serial = args.serial
    if not serial:
        local = ROOT / 'devices.local.json'
        bindings = json.loads(local.read_text()) if local.exists() else {}
        if not isinstance(bindings, dict):
            raise SafetyError('devices.local.json phải là object profile: serial.')
        serial = bindings.get(args.device)
    device = Device(args.device, serial)
    if args.command == 'status':
        print(args.device, device.model, 'online, identity đã xác minh')
    elif args.command == 'audit':
        audit(device)
    elif args.command in ('plan', 'debloat'):
        debloat(device, refresh(), args.package, args.apply, args.authorization, args.journal)
    else:
        if not args.journal:
            parser.error('rollback cần --journal cụ thể')
        rollback(device, args.journal, args.apply, args.authorization, args.package)


if __name__ == '__main__':
    try:
        main()
    except (SafetyError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('Dừng:', str(error) if isinstance(error, SafetyError) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
