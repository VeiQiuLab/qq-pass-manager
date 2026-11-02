"""Isolated real-widget self-test used by source and frozen executable alike."""
import csv
import json
import platform
import tempfile
import tkinter as tk
from pathlib import Path

from core import Store


def run(report_path):
    from app import App, messagebox, filedialog, prepare_tk
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    original = (messagebox.showinfo, messagebox.showerror, messagebox.askyesno, filedialog.asksaveasfilename)
    messagebox.showinfo = lambda *a, **kw: None
    messagebox.showerror = lambda *a, **kw: errors.append(str(a[1]))
    messagebox.askyesno = lambda *a, **kw: True
    root = None
    try:
        with tempfile.TemporaryDirectory(prefix='qqpass-selftest-', dir=report_path.parent) as folder:
            store = Store(Path(folder)/'data')
            prepare_tk()
            root = tk.Tk()
            root.withdraw()
            app = App(root, store)
            root.update()
            root.deiconify()
            root.update()
            assert root.winfo_ismapped()
            assert root.winfo_width() >= 1120 and root.winfo_height() >= 760
            checks.append('真实窗口已映射并完成布局，默认尺寸符合最小可用范围')
            a, b = app.panels['A'], app.panels['B']
            for panel, name in ((a,'A测试申请人'),(b,'B测试申请人')):
                panel.name.set(name)
                panel.qq.set('12345678')
                panel.notes.insert('1.0', panel.group+'独有备注')
                panel.issue_button.invoke()
                root.update()
                assert len(panel.tree.get_children()) == 1
            assert not errors, errors
            checks.append('真实 Tk 按钮发放，A/B 表单与记录独立')
            ar, br = store.list_records('A')[0], store.list_records('B')[0]
            b.check_token.set(ar['token'])
            b.verify_button.invoke()
            assert errors and b.last_verified is None
            errors.clear()
            b.check_token.set(br['token'])
            a.check_qq.set('87654321')
            a.verify_button.invoke()
            assert errors and a.last_verified is None
            errors.clear()
            a.check_qq.set(ar['qq'])
            a.verify_button.invoke()
            root.update()
            assert not errors, errors
            assert store.get('A',ar['id'])['status'] == 'verified'
            assert store.get('A',ar['id'])['used_at'] is None
            checks.append('界面拒绝跨群与错误 QQ；核验不消耗')
            a.consume_button.invoke()
            assert errors
            errors.clear()
            assert store.get('A',ar['id'])['status'] == 'verified'
            a.manual.set(True)
            a.check_token.set('99999999')
            assert not a.manual.get() and a.last_verified is None
            a.consume_button.invoke()
            assert errors
            errors.clear()
            a.check_token.set(ar['token'])
            a.verify_button.invoke()
            a.manual.set(True)
            app.tabs.select(b)
            root.update()
            assert not a.manual.get() and a.last_verified is None
            app.tabs.select(a)
            root.update()
            checks.append('未勾选确认拒绝核销；变更输入/切换群清除人工确认')
            a.verify_button.invoke()
            a.manual.set(True)
            a.consume_button.invoke()
            root.update()
            assert not errors, errors
            assert store.get('A',ar['id'])['status'] == 'used'
            assert store.get('B',br['id'])['status'] == 'pending'
            a.consume_button.invoke()
            assert errors
            errors.clear()
            checks.append('人工确认后核销一次，重复核销拒绝，B 群状态不变')
            a.search.set('B独有备注')
            assert not a.tree.get_children()
            a.search.set('')
            a.filter.set('已核销')
            assert len(a.tree.get_children()) == 1
            checks.append('界面搜索与状态筛选仅作用当前群')
            export = Path(folder)/'a.csv'
            filedialog.asksaveasfilename = lambda **kw: str(export)
            a.export()
            with export.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 1 and rows[0]['群组'] == 'A群'
            assert br['token'] not in export.read_text(encoding='utf-8-sig')
            checks.append('界面 CSV 导出遵从当前群与筛选')
            b.tree.selection_set(str(br['id']))
            b.revoke()
            assert store.get('B',br['id'])['status'] == 'revoked'
            b.verify_button.invoke()
            assert errors
            errors.clear()
            checks.append('界面撤销后核验拒绝')
            app.close()
            root = None
            reopened = Store(Path(folder)/'data')
            assert reopened.get('A',ar['id'])['status'] == 'used'
            assert reopened.get('B',br['id'])['status'] == 'revoked'
            checks.append('关闭真实 Tk 后重开数据库，状态持久化')
        report = {'ok':True,'platform':platform.platform(),'tk':tk.TkVersion,'checks':checks,'synthetic_data_only':True,'qq_client_tested':False}
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return report
    finally:
        if root is not None:
            root.destroy()
        messagebox.showinfo, messagebox.showerror, messagebox.askyesno, filedialog.asksaveasfilename = original
