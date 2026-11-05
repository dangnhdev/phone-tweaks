import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import phone_tweaks as t

A, B = t.CANDIDATES
REAL_EVIDENCE = t.evidence


class Adb:
    def __init__(self):
        self.models = {'usb1': 'SM-X700', 'phone:5555': 'SM-S918B'}
        self.hardware = {'usb1': 'hardware-tab', 'phone:5555': 'hardware-phone'}
        self.states = {A: 0, B: 1}
        self.calls = []
        self.writes = []
        self.offline = False
        self.fail = None
        self.dispatch_then_fail = False

    def run(self, argv, **kwargs):
        self.calls.append(argv)
        if argv[:2] == ['adb', 'devices']:
            return subprocess.CompletedProcess(argv, 0, 'List of devices attached\nusb1 %s usb:1\nphone:5555 device\n' % ('offline' if self.offline else 'device'), '')
        assert argv[:2] == ['adb', '-s'], argv
        serial, command = argv[2], argv[4:]
        if command[0] == 'getprop':
            value = self.models[serial] if command[1] == 'ro.product.model' else self.hardware[serial]
        elif command[:3] == ['pm', 'list', 'packages']:
            value = '\n'.join('package:' + p for p in self.states)
        elif command[:2] == ['dumpsys', 'package']:
            value = '  User 0: installed=true hidden=false enabled=%d' % self.states[command[2]]
        elif command[0] == 'pm':
            state = {v: k for k, v in t.STATES.items()}[command[1]]
            package = command[-1]
            self.writes.append((serial, package, state))
            if package == self.fail:
                if self.dispatch_then_fail:
                    self.states[package] = state
                value = 'Error: failed to change state'
            else:
                self.states[package] = state
                value = 'Package %s new state: %s' % (package, t.LABELS[state])
        else:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(argv, 0, value, '')


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.adb = Adb()
        self.patches = [patch.object(t, 'ROOT', self.root),
                        patch.object(t.subprocess, 'run', self.adb.run),
                        patch.object(t, 'evidence', lambda refs, package: refs)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.device = t.Device('tab-s8', 'usb1')
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def apply(self, selected, authorization='approved'):
        plan = t.debloat(self.device, {}, selected, False, '')
        return t.debloat(self.device, {}, selected, True, authorization, plan)

    def test_cli_debloat_defaults_to_dry_run(self):
        with patch.object(t, 'refresh', return_value={}):
            t.main(['debloat', '--device', 'tab-s8', '--serial', 'usb1', '--package', A])
        self.assertEqual(self.adb.writes, [])

    def test_changed_reference_rating_blocks_candidate(self):
        for rating in ('Advanced', 'Recommended'):
            with patch.object(t, 'source_text', side_effect=[A, json.dumps({A: {'removal': rating}})]):
                refs = {name: {'commit': 'fixture'} for name in t.SOURCES}
                if rating == 'Advanced':
                    with self.assertRaises(t.SafetyError):
                        REAL_EVIDENCE(refs, A)
                else:
                    self.assertIn('uad-ng', REAL_EVIDENCE(refs, A))

    def test_write_ahead_journal_precedes_dispatch(self):
        original_run = self.adb.run
        def checked(argv, **kwargs):
            if len(argv) > 5 and argv[4:6] == ['pm', 'disable-user']:
                path = next(p for p in (self.root / 'backups').rglob('journal.json')
                            if json.loads(p.read_text())['kind'] == 'debloat')
                entry = json.loads(path.read_text())['entries'][-1]
                self.assertEqual(entry['status'], 'pending')
                self.assertEqual(entry['original'], 0)
            return original_run(argv, **kwargs)
        with patch.object(t.subprocess, 'run', checked):
            self.apply([A])
        self.assertEqual(self.adb.states[A], 3)

    def test_two_devices_explicit_selection(self):
        phone = t.Device('s23-ultra', 'phone:5555')
        self.assertEqual(phone.model, 'SM-S918B')
        self.assertEqual(self.device.model, 'SM-X700')
        for argv in self.adb.calls:
            if argv[:2] != ['adb', 'devices']:
                self.assertEqual(argv[1], '-s')
        with self.assertRaises(t.SafetyError):
            t.Device('tab-s8', None)

    def test_mismatch_offline_and_unauthorized(self):
        self.adb.models['usb1'] = 'SM-P610'
        with self.assertRaises(t.SafetyError):
            t.Device('tab-s8', 'usb1')
        self.adb.offline = True
        with self.assertRaises(t.SafetyError):
            t.Device('tab-s8', 'usb1')
        with patch.object(t, 'run', return_value='List of devices attached\nusb1 unauthorized usb:1'):
            with self.assertRaises(t.SafetyError):
                t.Device('tab-s8', 'usb1')
        self.assertEqual(self.adb.writes, [])

    def test_default_plan_and_rollback_no_writes(self):
        path = t.debloat(self.device, {}, [], False, '')
        with self.assertRaises(t.SafetyError):
            t.rollback(self.device, path, False, '')
        self.assertEqual(self.adb.writes, [])
        self.assertEqual(json.loads(path.read_text())['entries'], [])

    def test_apply_requires_selection_and_authorization(self):
        for selected, auth in [([], 'approved'), ([A], ''), (['com.android.phone'], 'approved')]:
            with self.assertRaises(t.SafetyError):
                t.debloat(self.device, {}, selected, True, auth)
        self.assertEqual(self.adb.writes, [])

    def test_failed_refresh_blocks_even_with_cache(self):
        cache = self.root / '.cache/references'
        cache.mkdir(parents=True)
        (cache / 'manifest.json').write_text('{"stale":true}')
        with patch.object(t, 'run', side_effect=t.SafetyError('network failure')):
            with self.assertRaises(t.SafetyError):
                t.refresh()
        with patch.object(t, 'refresh', side_effect=t.SafetyError('network failure')):
            with self.assertRaises(t.SafetyError):
                t.main(['debloat', '--device', 'tab-s8', '--serial', 'usb1',
                        '--package', A, '--apply', '--authorization', 'approved'])
        self.assertEqual(self.adb.writes, [])

    def test_partial_failure_write_ahead_and_rollback(self):
        self.adb.fail = B
        self.adb.dispatch_then_fail = True
        with self.assertRaises(t.SafetyError):
            self.apply([A, B], 'explicit user decision')
        path = next(p for p in (self.root / 'backups').rglob('journal.json')
                    if json.loads(p.read_text())['kind'] == 'debloat')
        entries = json.loads(path.read_text())['entries']
        self.assertEqual([(e['original'], e['status']) for e in entries], [(0, 'disabled'), (1, 'uncertain')])
        self.adb.fail = None
        t.rollback(self.device, path, True, 'restore approved')
        self.assertEqual(self.adb.states, {A: 0, B: 1})
        before = len(self.adb.writes)
        t.rollback(self.device, path, True, 'retry')
        self.assertEqual(len(self.adb.writes), before)

    def test_all_original_states_exact(self):
        for original in t.STATES:
            self.adb.states[A] = original
            path = self.apply([A])
            data = json.loads(path.read_text())
            if original in (2, 3, 4):
                self.assertEqual(data['entries'], [])
            t.rollback(self.device, path, True, 'restore')
            self.assertEqual(self.adb.states[A], original)

    def test_wrong_hardware_or_model_cannot_rollback(self):
        path = self.apply([A])
        self.adb.hardware['usb1'] = 'other-tab'
        other = t.Device('tab-s8', 'usb1')
        before = len(self.adb.writes)
        with self.assertRaises(t.SafetyError):
            t.rollback(other, path, True, 'approved')
        with self.assertRaises(t.SafetyError):
            self.device.change(A, 0)
        self.assertEqual(len(self.adb.writes), before)

    def test_stdout_success_without_readback_not_accepted(self):
        with patch.object(self.device, 'state', return_value=0):
            with self.assertRaises(t.SafetyError):
                self.device.change(A, 3)

    def test_apply_requires_reviewed_plan(self):
        with self.assertRaises(t.SafetyError):
            t.debloat(self.device, {}, [A], True, 'approved')
        self.assertEqual(self.adb.writes, [])

    def test_reviewed_plan_rejects_replacement_hardware(self):
        plan = t.debloat(self.device, {}, [A], False, '')
        self.adb.hardware['usb1'] = 'replacement-tab'
        other = t.Device('tab-s8', 'usb1')
        with self.assertRaises(t.SafetyError):
            t.debloat(other, {}, [A], True, 'approved', plan)
        self.assertEqual(self.adb.writes, [])

    def test_rollback_swap_does_not_mark_restored(self):
        journal = self.apply([A])
        self.adb.hardware['usb1'] = 'replacement-tab'
        self.adb.states[A] = 0
        with self.assertRaises(t.SafetyError):
            t.rollback(self.device, journal, True, 'restore')
        self.assertEqual(json.loads(journal.read_text())['entries'][0]['status'], 'disabled')
        self.adb.hardware['usb1'] = 'hardware-tab'
        self.adb.states[A] = 3
        t.rollback(self.device, journal, True, 'restore')
        self.assertEqual(self.adb.states[A], 0)

    def test_duplicate_selection_rejected_before_any_write(self):
        with self.assertRaises(t.SafetyError):
            self.apply([A, A, B])
        self.assertEqual(self.adb.writes, [])

    def test_new_fetch_timestamp_accepts_same_source_commit(self):
        refs = {'source': {'url': 'https://example.test', 'commit': 'same',
                           'path': 'list.txt', 'fetched_utc': 'first'}}
        plan = t.debloat(self.device, refs, [A], False, '')
        refs['source']['fetched_utc'] = 'later'
        journal = t.debloat(self.device, refs, [A], True, 'approved', plan)
        self.assertEqual(self.adb.states[A], 3)
        self.assertEqual(json.loads(journal.read_text())['references']['source']['fetched_utc'], 'later')

    def test_new_source_commit_invalidates_reviewed_plan(self):
        refs = {'source': {'url': 'https://example.test', 'commit': 'old'}}
        plan = t.debloat(self.device, refs, [A], False, '')
        refs['source']['commit'] = 'new'
        with self.assertRaises(t.SafetyError):
            t.debloat(self.device, refs, [A], True, 'approved', plan)
        self.assertEqual(self.adb.writes, [])

    def test_changed_state_invalidates_reviewed_plan(self):
        plan = t.debloat(self.device, {}, [A], False, '')
        self.adb.states[A] = 1
        with self.assertRaises(t.SafetyError):
            t.debloat(self.device, {}, [A], True, 'approved', plan)
        self.assertEqual(self.adb.writes, [])

    def test_rollback_preflight_and_selected_recovery(self):
        journal = self.apply([A, B])
        self.adb.states[A] = 2
        before = len(self.adb.writes)
        with self.assertRaises(t.SafetyError):
            t.rollback(self.device, journal, True, 'restore')
        self.assertEqual(len(self.adb.writes), before)
        t.rollback(self.device, journal, True, 'restore B only', [B])
        self.assertEqual(self.adb.states, {A: 2, B: 1})
        self.assertEqual(self.adb.writes[before:], [('usb1', B, 1)])

    def test_cli_rollback_works_without_network(self):
        journal = self.apply([A])
        with patch.object(t, 'refresh', side_effect=AssertionError('rollback fetched network')):
            t.main(['rollback', '--device', 'tab-s8', '--serial', 'usb1',
                    '--journal', str(journal), '--package', A,
                    '--apply', '--authorization', 'restore A'])
        self.assertEqual(self.adb.states[A], 0)

    def test_irrelevant_cli_flags_rejected(self):
        cases = [['status', '--device', 'tab-s8', '--package', A],
                 ['refresh', '--device', 'tab-s8'],
                 ['plan', '--device', 'tab-s8', '--journal', '/nonexistent'],
                 ['debloat', '--device', 'tab-s8', '--journal', '/nonexistent']]
        for args in cases:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                t.main(args)
            self.assertEqual(exc.exception.code, 2)
        self.assertEqual(self.adb.writes, [])

    def test_audit_records_timeout_and_decode_failures(self):
        for error in (subprocess.TimeoutExpired('adb', 90),
                      UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid')):
            with patch.object(self.device, 'shell', side_effect=error), patch.object(self.device, 'validate'):
                with self.assertRaises(t.SafetyError):
                    t.audit(self.device)
        records = list((self.root / 'backups').rglob('audit-status.json'))
        self.assertEqual(len(records), 2)
        for record in records:
            data = json.loads(record.read_text())
            self.assertFalse(data['complete'])
            self.assertIn('df', data['failed'])

    def test_package_named_error_is_valid(self):
        self.adb.states['io.sentry.error'] = 0
        self.assertIn('io.sentry.error', self.device.packages())
        t.make_plan(self.device, {}, [A])

    def test_bad_bindings_and_journal_shapes_fail_cleanly(self):
        for value in ([], {'tab-s8': 12345}):
            (self.root / 'devices.local.json').write_text(json.dumps(value))
            with self.assertRaises(t.SafetyError):
                t.main(['status', '--device', 'tab-s8'])
        for change in ({'entries': [1]}, {'entries': [{'package': []}]},
                       {'references': []}, {'packages': None}):
            path = t.debloat(self.device, {}, [A], False, '')
            data = json.loads(path.read_text())
            data.update(change)
            path.write_text(json.dumps(data))
            with self.assertRaises(t.SafetyError):
                t.read_record(path)

    def test_stale_restored_journal_does_not_overwrite_new_change(self):
        path = self.apply([A])
        t.rollback(self.device, path, True, 'approved')
        self.adb.states[A] = 3
        before = len(self.adb.writes)
        with self.assertRaises(t.SafetyError):
            t.rollback(self.device, path, True, 'approved')
        self.assertEqual(len(self.adb.writes), before)


if __name__ == '__main__':
    unittest.main()
