import csv
import json
import subprocess
import sys
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from core import Store, RuleError, TTL, ALPHABET, FIRST


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.now = 1_800_000_000
        self.store = Store(self.folder, lambda: self.now)

    def issue(self, group='A', qq='12345678', name='申请者甲', notes='仅本群备注'):
        return self.store.issue(group, qq, name, notes)

    def test_secrets_eight_characters_and_24_hours(self):
        with patch('core.secrets.choice', wraps=__import__('secrets').choice) as choice:
            row = self.issue()
            self.assertEqual(choice.call_count, 8)
        self.assertEqual(len(row['token']), 8)
        self.assertTrue(set(row['token']) <= set(ALPHABET))
        self.assertFalse(set(ALPHABET) & set('01OIlBSZ8'))
        self.assertEqual(row['expires_at'] - row['issued_at'], TTL)
        self.assertEqual(row['status'], 'pending')

    def test_group_token_namespaces_never_overlap(self):
        self.assertTrue(set(FIRST['A']).isdisjoint(FIRST['B']))
        for group in ('A', 'B'):
            rows = [self.issue(group, str(12345000 + n)) for n in range(120)]
            self.assertEqual(len({r['token'] for r in rows}), 120)
            self.assertTrue(all(r['token'][0] in FIRST[group] for r in rows))

    def test_cross_group_refused_even_same_qq(self):
        a = self.issue('A')
        b = self.issue('B')
        for source, target in ((a,'B'), (b,'A')):
            with self.assertRaises(RuleError):
                self.store.verify(target,source['qq'],source['token'])
            with self.assertRaises(RuleError):
                self.store.consume(target,source['qq'],source['token'],manual_approved=True)
        self.assertEqual(self.store.get('A',a['id'])['status'], 'pending')
        self.assertEqual(self.store.get('B',b['id'])['status'], 'pending')

    def test_wrong_qq_and_wrong_token_never_pass(self):
        a = self.issue()
        for qq, token in [('87654321',a['token']), (a['qq'],'99999999'), (a['qq'],"' OR 1=1")]:
            with self.assertRaises(RuleError):
                self.store.verify('A',qq,token)
            with self.assertRaises(RuleError):
                self.store.consume('A',qq,token,manual_approved=True)
        self.assertIsNone(self.store.get('A',a['id'])['verified_at'])

    def test_verify_does_not_consume_and_is_repeatable(self):
        a = self.issue()
        for _ in range(3):
            row = self.store.verify('A',a['qq'],a['token'].lower())
            self.assertEqual(row['status'],'verified')
            self.assertEqual(row['state'],'active')
            self.assertIsNone(row['used_at'])

    def test_consumption_requires_verification_and_manual_approval(self):
        a = self.issue()
        with self.assertRaises(RuleError):
            self.store.consume('A',a['qq'],a['token'],manual_approved=True)
        self.store.verify('A',a['qq'],a['token'])
        for approved in (False, None, 1, 'yes'):
            with self.assertRaises(RuleError):
                self.store.consume('A',a['qq'],a['token'],manual_approved=approved)
        self.assertEqual(self.store.get('A',a['id'])['status'],'verified')
        result = self.store.consume('A',a['qq'],a['token'],manual_approved=True)
        self.assertEqual(result['status'],'used')
        self.assertEqual(result['used_at'], self.now)

    def test_duplicate_consumption_and_verify_used_rejected(self):
        a = self.issue()
        self.store.verify('A',a['qq'],a['token'])
        self.store.consume('A',a['qq'],a['token'],manual_approved=True)
        for action in (lambda: self.store.consume('A',a['qq'],a['token'],manual_approved=True), lambda: self.store.verify('A',a['qq'],a['token']), lambda: self.store.revoke('A',a['id'])):
            with self.assertRaises(RuleError):
                action()

    def test_expiry_exact_boundary(self):
        a = self.issue()
        self.now += TTL - 1
        self.store.verify('A',a['qq'],a['token'])
        self.now += 1
        self.assertEqual(self.store.get('A',a['id'])['status'],'expired')
        with self.assertRaises(RuleError):
            self.store.verify('A',a['qq'],a['token'])
        with self.assertRaises(RuleError):
            self.store.consume('A',a['qq'],a['token'],manual_approved=True)

    def test_expiry_rechecked_after_verification(self):
        a = self.issue()
        self.store.verify('A',a['qq'],a['token'])
        self.now += TTL + 10
        with self.assertRaises(RuleError):
            self.store.consume('A',a['qq'],a['token'],manual_approved=True)

    def test_revoked_code_rejected_for_verify_and_consume(self):
        a = self.issue()
        self.store.verify('A',a['qq'],a['token'])
        self.store.revoke('A',a['id'])
        self.assertEqual(self.store.get('A',a['id'])['status'],'revoked')
        with self.assertRaises(RuleError):
            self.store.verify('A',a['qq'],a['token'])
        with self.assertRaises(RuleError):
            self.store.consume('A',a['qq'],a['token'],manual_approved=True)

    def test_restart_persists_all_states_and_notes(self):
        a = self.issue()
        b = self.issue('B')
        c = self.issue('A','23456789','申请者乙','带换行\n持久化')
        self.store.verify('A',a['qq'],a['token'])
        self.store.consume('A',a['qq'],a['token'],manual_approved=True)
        self.store.revoke('B',b['id'])
        del self.store
        self.store = Store(self.folder, lambda: self.now)
        self.assertEqual(self.store.get('A',a['id'])['status'],'used')
        self.assertEqual(self.store.get('B',b['id'])['status'],'revoked')
        self.assertEqual(self.store.get('A',c['id'])['notes'],'带换行\n持久化')
        with self.assertRaises(RuleError):
            self.store.consume('A',a['qq'],a['token'],manual_approved=True)
        self.now += TTL
        self.assertEqual(Store(self.folder, lambda: self.now).get('A',c['id'])['status'],'expired')

    def test_persistence_across_separate_processes(self):
        setup = """
import sys
from core import Store
s=Store(sys.argv[1])
a=s.issue('A','12345678','独立进程甲','重启备注')
b=s.issue('B','12345678','独立进程乙','B群备注')
s.verify('A',a['qq'],a['token'])
s.consume('A',a['qq'],a['token'],manual_approved=True)
s.revoke('B',b['id'])
"""
        subprocess.run([sys.executable,'-c',setup,str(self.folder)],check=True,timeout=20)
        read = """
import sys,json
from core import Store
s=Store(sys.argv[1])
print(json.dumps([s.list_records('A'),s.list_records('B')]))
"""
        result = subprocess.run([sys.executable,'-c',read,str(self.folder)],capture_output=True,text=True,check=True,timeout=20)
        a,b = json.loads(result.stdout)
        self.assertEqual(a[0]['status'],'used')
        self.assertEqual(b[0]['status'],'revoked')
        self.assertEqual(a[0]['notes'],'重启备注')
        self.assertEqual(b[0]['notes'],'B群备注')

    def test_same_qq_separate_applicant_notes_and_state(self):
        a = self.issue('A',name='A申请人',notes='A私有备注')
        b = self.issue('B',name='B申请人',notes='B私有备注')
        self.store.edit('A',a['id'],'A修改','A备注修改')
        self.store.verify('A',a['qq'],a['token'])
        self.store.revoke('A',a['id'])
        self.assertEqual(self.store.get('B',b['id'])['name'],'B申请人')
        self.assertEqual(self.store.get('B',b['id'])['notes'],'B私有备注')
        self.assertEqual(self.store.get('B',b['id'])['status'],'pending')
        self.assertEqual(self.store.list_records('B','A备注修改'),[])
        self.assertEqual(self.store.list_records('A','B私有备注'),[])

    def test_search_and_status_filter_are_group_scoped(self):
        a = self.issue('A',name='张三',notes='班级甲')
        self.issue('B',name='张三',notes='班级乙')
        self.assertEqual(len(self.store.list_records('A','张三')),1)
        self.assertEqual(len(self.store.list_records('A',a['qq'])),1)
        self.assertEqual(len(self.store.list_records('A',a['token'].lower())),1)
        self.assertEqual(len(self.store.list_records('A','班级乙')),0)
        self.store.verify('A',a['qq'],a['token'])
        self.assertEqual(len(self.store.list_records('A',status='verified')),1)
        self.assertEqual(len(self.store.list_records('B',status='verified')),0)
        self.assertEqual(len(self.store.list_records('A',status='pending')),0)

    def test_csv_all_groups_isolated_with_unicode_quotes_newlines(self):
        a = self.issue('A',name='甲,同学',notes='备注"双引号"\n下一行')
        b = self.issue('B',name='乙同学',notes='B独有')
        for group, own, other in [('A',a,b),('B',b,a)]:
            path = self.folder / f'{group}.csv'
            self.assertEqual(self.store.export_csv(group,path),1)
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            with path.open(encoding='utf-8-sig',newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]['群组'],group+'群')
            self.assertEqual(rows[0]['口令'],own['token'])
            self.assertEqual(rows[0]['备注'],own['notes'])
            self.assertNotIn(other['token'],path.read_text(encoding='utf-8-sig'))
            self.assertNotIn(other['name'],path.read_text(encoding='utf-8-sig'))

    def test_csv_respects_current_search_status_and_empty_header(self):
        a = self.issue('A',name='甲')
        self.issue('A','23456789','乙')
        self.issue('B','34567890','甲')
        self.store.verify('A',a['qq'],a['token'])
        path = self.folder / 'filtered.csv'
        self.assertEqual(self.store.export_csv('A',path,'甲','verified'),1)
        self.assertEqual(self.store.export_csv('A',path,'甲','pending'),0)
        self.assertEqual(len(path.read_text(encoding='utf-8-sig').splitlines()),1)

    def test_csv_formula_injection_is_neutralized(self):
        self.issue(name='=1+1',notes=' \t@SUM(1,2)')
        path = self.folder / 'safe.csv'
        self.store.export_csv('A',path)
        with path.open(encoding='utf-8-sig',newline='') as f:
            row = list(csv.DictReader(f))[0]
        self.assertEqual(row['申请人'],"'=1+1")
        self.assertTrue(row['备注'].startswith("'"))

    def test_duplicate_qq_does_not_issue_second_active_code(self):
        self.issue()
        with self.assertRaises(RuleError):
            self.issue()
        self.assertEqual(len(self.store.list_records('A')),1)

    def test_reissue_revokes_old_retains_history_and_group_isolation(self):
        a = self.issue()
        b = self.issue('B')
        self.store.verify('A',a['qq'],a['token'])
        new = self.store.issue('A',a['qq'],'申请者甲','新备注',reissue=True)
        self.assertNotEqual(new['token'],a['token'])
        self.assertEqual(new['status'],'pending')
        self.assertEqual(self.store.get('A',a['id'])['status'],'revoked')
        self.assertEqual(self.store.get('B',b['id'])['status'],'pending')
        with self.assertRaises(RuleError):
            self.store.verify('A',a['qq'],a['token'])
        self.assertEqual(len(self.store.list_records('A')),2)

    def test_used_applicant_cannot_be_reissued(self):
        a = self.issue()
        self.store.verify('A',a['qq'],a['token'])
        self.store.consume('A',a['qq'],a['token'],manual_approved=True)
        with self.assertRaises(RuleError):
            self.store.issue('A',a['qq'],'甲',reissue=True)

    def test_validation_no_records_created_on_invalid_input(self):
        for qq in ['012345','abcde','１２３４５','1234','1'*13]:
            with self.assertRaises(RuleError):
                self.issue(qq=qq)
        for name, notes in [('', ''),('x'*101,''),('甲','x'*2001)]:
            with self.assertRaises(RuleError):
                self.issue(name=name,notes=notes)
        self.assertEqual(self.store.list_records('A'),[])
        with self.assertRaises(RuleError):
            self.store.list_records('C')
        with self.assertRaises(RuleError):
            self.store.issue('C','12345','甲')

    def test_clock_rollback_rejected_after_restart(self):
        a = self.issue()
        self.now += 200
        self.store.verify('A',a['qq'],a['token'])
        self.now -= 100
        self.store = Store(self.folder, lambda: self.now)
        with self.assertRaises(RuleError):
            self.store.consume('A',a['qq'],a['token'],manual_approved=True)

    def test_two_concurrent_consumers_exactly_one_succeeds(self):
        a = self.issue()
        self.store.verify('A',a['qq'],a['token'])
        stores = [Store(self.folder, lambda: self.now) for _ in range(2)]
        barrier = threading.Barrier(2)
        results = []
        def consume(store):
            barrier.wait(timeout=5)
            try:
                store.consume('A',a['qq'],a['token'],manual_approved=True)
                results.append('used')
            except RuleError:
                results.append('refused')
        threads = [threading.Thread(target=consume,args=(s,)) for s in stores]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive())
        self.assertCountEqual(results,['used','refused'])
        with closing(sqlite3.connect(self.folder/'group_A.sqlite3')) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE kind='used'").fetchone()[0],1)

    def test_files_physically_separate_and_identity_guard(self):
        a = self.issue('A',name='A独有')
        self.issue('B',name='B独有')
        with closing(sqlite3.connect(self.folder/'group_B.sqlite3')) as db:
            self.assertIsNone(db.execute('SELECT * FROM codes WHERE token=?',(a['token'],)).fetchone())
            self.assertIsNone(db.execute("SELECT * FROM applicants WHERE name='A独有'").fetchone())
            db.execute("UPDATE meta SET value='A' WHERE key='group'")
            db.commit()
        with self.assertRaises(RuleError):
            Store(self.folder)

    def test_random_collision_retries_without_overwriting(self):
        with patch('core.secrets.choice',return_value='2'):
            a = self.issue()
        sequence = ['2']*8 + ['3']*8
        with patch('core.secrets.choice',side_effect=sequence):
            b = self.issue(qq='23456789')
        self.assertEqual(a['token'],'22222222')
        self.assertEqual(b['token'],'33333333')
        self.assertEqual(self.store.get('A',a['id'])['qq'],'12345678')


if __name__ == '__main__':
    unittest.main()
