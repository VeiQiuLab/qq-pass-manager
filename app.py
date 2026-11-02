"""Windows tkinter UI. No network or QQ automation capabilities."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import VERSION, STATES, Store, RuleError, default_directory, timestamp
from tk_startup import prepare_tk


class GroupPanel(ttk.Frame):
    def __init__(self, notebook, store, group):
        super().__init__(notebook, padding=14)
        self.store, self.group = store, group
        self.selected_id = None
        self.last_verified = None
        self.name = tk.StringVar(self)
        self.qq = tk.StringVar(self)
        self.check_qq = tk.StringVar(self)
        self.check_token = tk.StringVar(self)
        self.search = tk.StringVar(self)
        self.filter = tk.StringVar(self, '全部状态')
        self.manual = tk.BooleanVar(self, False)
        self.result = tk.StringVar(self, '请核对当前群、申请者 QQ 号与口令。')
        self.summary = tk.StringVar(self)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky='ew', pady=(0,10))
        ttk.Label(top, text=f'{group} 群 · 独立入群审核', style='Title.TLabel').pack(side='left')
        ttk.Label(top, textvariable=self.summary).pack(side='right')
        upper = ttk.Frame(self)
        upper.grid(row=1, column=0, sticky='ew')
        upper.columnconfigure(0, weight=1)
        upper.columnconfigure(1, weight=1)
        form = ttk.LabelFrame(upper, text=f'{group} 群申请人与口令', padding=12)
        form.grid(row=0, column=0, sticky='nsew', padx=(0,8))
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text='申请人').grid(row=0, column=0, sticky='w')
        self.name_entry = ttk.Entry(form, textvariable=self.name)
        self.name_entry.grid(row=0, column=1, sticky='ew', pady=3)
        ttk.Label(form, text='QQ 号').grid(row=1, column=0, sticky='w')
        self.qq_entry = ttk.Entry(form, textvariable=self.qq)
        self.qq_entry.grid(row=1, column=1, sticky='ew', pady=3)
        ttk.Label(form, text='备注').grid(row=2, column=0, sticky='nw')
        self.notes = tk.Text(form, height=3, wrap='word', font=('Microsoft YaHei UI', 10), relief='solid', borderwidth=1)
        self.notes.grid(row=2, column=1, sticky='ew', pady=3)
        buttons = ttk.Frame(form)
        buttons.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(8,0))
        self.issue_button = ttk.Button(buttons, text='新建并发放', command=self.issue)
        self.issue_button.pack(side='left', padx=(0,5))
        ttk.Button(buttons, text='保存姓名/备注', command=self.edit).pack(side='left', padx=5)
        ttk.Button(buttons, text='清空表单', command=self.clear).pack(side='left', padx=5)
        actions = ttk.Frame(form)
        actions.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(6,0))
        ttk.Button(actions, text='撤销所选口令', command=self.revoke).pack(side='left', padx=(0,5))
        ttk.Button(actions, text='撤销旧令并重发', command=self.reissue).pack(side='left', padx=5)
        ttk.Button(actions, text='复制所选口令', command=self.copy).pack(side='left', padx=5)
        check = ttk.LabelFrame(upper, text=f'{group} 群核验 / 人工批准后核销', padding=12)
        check.grid(row=0, column=1, sticky='nsew', padx=(8,0))
        check.columnconfigure(1, weight=1)
        ttk.Label(check, text='申请者 QQ').grid(row=0, column=0, sticky='w')
        self.verify_qq_entry = ttk.Entry(check, textvariable=self.check_qq)
        self.verify_qq_entry.grid(row=0, column=1, sticky='ew', pady=3)
        ttk.Label(check, text='8 位口令').grid(row=1, column=0, sticky='w')
        self.verify_token_entry = ttk.Entry(check, textvariable=self.check_token, font=('Consolas', 13))
        self.verify_token_entry.grid(row=1, column=1, sticky='ew', pady=3)
        self.verify_button = ttk.Button(check, text='① 核验（不消耗口令）', command=self.verify)
        self.verify_button.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(8,5))
        ttk.Checkbutton(check, variable=self.manual, text=f'② 我已在 QQ 客户端核对并批准加入 {group} 群').grid(row=3, column=0, columnspan=2, sticky='w', pady=4)
        self.consume_button = ttk.Button(check, text='③ 确认人工批准后核销', command=self.consume)
        self.consume_button.grid(row=4, column=0, columnspan=2, sticky='ew', pady=4)
        ttk.Label(check, textvariable=self.result, wraplength=470, foreground='#1d4c71').grid(row=5, column=0, columnspan=2, sticky='w', pady=(6,0))
        for var in (self.check_qq, self.check_token):
            var.trace_add('write', self.invalidate)

        lower = ttk.Frame(self)
        lower.grid(row=2, column=0, sticky='nsew', pady=(14,0))
        lower.rowconfigure(1, weight=1)
        lower.columnconfigure(0, weight=1)
        bar = ttk.Frame(lower)
        bar.grid(row=0, column=0, sticky='ew', pady=(0,8))
        ttk.Label(bar, text=f'仅搜索 {group} 群').pack(side='left')
        ttk.Entry(bar, textvariable=self.search, width=25).pack(side='left', padx=8)
        ttk.Combobox(bar, textvariable=self.filter, values=['全部状态', *STATES.values()], state='readonly', width=18).pack(side='left', padx=5)
        ttk.Button(bar, text='刷新', command=self.refresh).pack(side='left', padx=5)
        ttk.Button(bar, text=f'导出 {group} 群当前筛选 CSV', command=self.export).pack(side='right')
        self.search.trace_add('write', lambda *_: self.refresh())
        self.filter.trace_add('write', lambda *_: self.refresh())
        table = ttk.Frame(lower)
        table.grid(row=1, column=0, sticky='nsew')
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = ('name','qq','token','status','expires','verified','used','notes')
        self.tree = ttk.Treeview(table, columns=columns, show='headings', selectmode='browse', height=9)
        widths = (110,115,100,140,175,175,175,220)
        for key, title, width in zip(columns, ('申请人','QQ 号','口令','状态','到期时间','最近核验','核销时间','备注'), widths):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=80, stretch=key in ('name','notes'))
        self.tree.grid(row=0, column=0, sticky='nsew')
        vs = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        vs.grid(row=0, column=1, sticky='ns')
        hs = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        hs.grid(row=1, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.tag_configure('used', foreground='#416b42')
        self.tree.tag_configure('revoked', foreground='#8a3c3c')
        self.tree.tag_configure('expired', foreground='#777777')
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.detail = tk.StringVar(self, '选择记录可查看时间并编辑备注；核销记录保留，不提供删除。')
        ttk.Label(lower, textvariable=self.detail, wraplength=1070).grid(row=2, column=0, sticky='w', pady=6)
        self.refresh()

    def invalidate(self, *_):
        self.last_verified = None
        self.manual.set(False)
        self.result.set('信息已变更，请重新核验；核验不会消耗口令。')

    def on_leave(self):
        self.invalidate()

    def form_notes(self):
        return self.notes.get('1.0','end-1c')

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            raise RuleError('请先选择当前群的一条记录。')
        return self.store.get(self.group, int(selection[0]))

    def show_error(self, error):
        messagebox.showerror(f'{self.group} 群 · 操作未通过', str(error), parent=self)

    def run_action(self, action):
        try:
            return action()
        except (RuleError, OSError, sqlite3.Error) as error:
            self.show_error(error)
            return None

    def clear(self):
        self.selected_id = None
        self.tree.selection_remove(*self.tree.selection())
        self.name.set('')
        self.qq.set('')
        self.notes.delete('1.0','end')
        self.check_qq.set('')
        self.check_token.set('')
        self.qq_entry.configure(state='normal')
        self.name_entry.focus_set()

    def populate(self, row):
        self.selected_id = row['id']
        self.name.set(row['name'])
        self.qq.set(row['qq'])
        self.qq_entry.configure(state='readonly')
        self.notes.delete('1.0','end')
        self.notes.insert('1.0', row['notes'])
        self.check_qq.set(row['qq'])
        self.check_token.set(row['token'])
        self.detail.set(f"{self.group} 群记录 #{row['id']}   发放：{timestamp(row['issued_at'])}   到期：{timestamp(row['expires_at'])}   撤销：{timestamp(row['revoked_at']) or '—'}")

    def on_select(self, _=None):
        if not self.tree.selection():
            return
        cid = int(self.tree.selection()[0])
        if self.selected_id == cid:
            return
        self.run_action(lambda: self.populate(self.selected()))

    def filter_key(self):
        return next((k for k,v in STATES.items() if v == self.filter.get()), 'all')

    def refresh(self, select_id=None):
        current = self.tree.selection()
        rows = self.store.list_records(self.group, self.search.get(), self.filter_key())
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert('', 'end', iid=str(r['id']), values=(r['name'],r['qq'],r['token'],STATES[r['status']],timestamp(r['expires_at']),timestamp(r['verified_at']),timestamp(r['used_at']),r['notes'].replace('\n',' / ')), tags=(r['status'],))
        target = str(select_id) if select_id is not None else (current[0] if current else None)
        if target and self.tree.exists(target):
            self.tree.selection_set(target)
            if select_id is not None:
                self.populate(self.store.get(self.group, select_id))
        self.summary.set(f'当前显示 {len(rows)} 条 · 24 小时有效 · 单次使用')

    def issue(self):
        def action():
            row = self.store.issue(self.group, self.qq.get(), self.name.get(), self.form_notes())
            self.search.set('')
            self.filter.set('全部状态')
            self.refresh(row['id'])
            messagebox.showinfo(f'{self.group} 群 · 发放成功', f"QQ：{row['qq']}\n口令：{row['token']}\n到期：{timestamp(row['expires_at'])}\n请人工发送给申请者；本工具不会发送消息。", parent=self)
            return row
        return self.run_action(action)

    def edit(self):
        def action():
            row = self.selected()
            self.store.edit(self.group,row['id'], self.name.get(), self.form_notes())
            self.refresh()
            self.result.set('姓名与备注已保存，仅影响当前群该申请者的记录。')
        return self.run_action(action)

    def reissue(self):
        def action():
            row = self.selected()
            if not messagebox.askyesno(f'{self.group} 群 · 重发确认', f"QQ {row['qq']}：本群旧有效口令将立即撤销，历史保留。确定重发？", parent=self):
                return
            new = self.store.issue(self.group, row['qq'], self.name.get(), self.form_notes(), reissue=True)
            self.filter.set('全部状态')
            self.search.set('')
            self.refresh(new['id'])
            messagebox.showinfo('重发成功', f"{self.group} 群新口令：{new['token']}", parent=self)
        return self.run_action(action)

    def revoke(self):
        def action():
            row = self.selected()
            if messagebox.askyesno(f'{self.group} 群 · 撤销确认', f"撤销 QQ {row['qq']} 的口令 {row['token']}？撤销后不能恢复。", parent=self):
                self.store.revoke(self.group, row['id'])
                self.invalidate()
                self.refresh()
        return self.run_action(action)

    def copy(self):
        def action():
            row = self.selected()
            self.clipboard_clear()
            self.clipboard_append(row['token'])
            self.result.set(f"已复制 {self.group} 群所选口令；当前状态：{STATES[row['status']]}。")
        return self.run_action(action)

    def verify(self):
        self.invalidate()
        def action():
            row = self.store.verify(self.group, self.check_qq.get(), self.check_token.get())
            self.last_verified = (row['qq'], row['token'])
            self.refresh()
            self.result.set(f"核验通过：{row['name']} / {row['qq']}。未消耗，请去 QQ 客户端人工核对批准。")
            return row
        return self.run_action(action)

    def consume(self):
        def action():
            pair = (self.check_qq.get().strip(), self.check_token.get().strip().upper())
            if pair != self.last_verified:
                raise RuleError('请先在本界面核验当前 QQ 号与口令。')
            if not self.manual.get():
                raise RuleError('请先在 QQ 客户端人工核对并批准入群，再勾选确认。')
            if not messagebox.askyesno(f'{self.group} 群 · 最终核销确认', f"确认已在 QQ 客户端批准 QQ {pair[0]} 加入 {self.group} 群？\n核销后口令不可再次使用。", parent=self):
                return
            row = self.store.consume(self.group, *pair, manual_approved=True)
            self.invalidate()
            self.refresh()
            self.result.set(f"已核销：{self.group} 群 / QQ {row['qq']}，此口令不能再次使用。")
            return row
        result = self.run_action(action)
        if result is None:
            self.manual.set(False)
        return result

    def export(self):
        def action():
            path = filedialog.asksaveasfilename(parent=self, title=f'仅导出 {self.group} 群当前筛选', defaultextension='.csv', initialfile=f'{self.group}群_入群记录.csv', filetypes=[('CSV 文件','*.csv')])
            if path:
                count = self.store.export_csv(self.group, path, self.search.get(), self.filter_key())
                messagebox.showinfo('导出完成', f'仅导出 {self.group} 群当前筛选的 {count} 条记录。\nCSV 包含 QQ 号和口令，请妥善保管。', parent=self)
        return self.run_action(action)


class App:
    def __init__(self, root, store):
        self.root, self.store = root, store
        root.title(f'QQ群入群口令管理器 {VERSION} · 完全离线')
        root.geometry('1220x820')
        root.minsize(1120, 760)
        style = ttk.Style(root)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('.', font=('Microsoft YaHei UI', 10))
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 16, 'bold'))
        style.configure('Treeview', rowheight=30)
        style.configure('TButton', padding=(7,5))
        ttk.Label(root, text='流程：发放口令 → 核验（不消耗） → 在 QQ 客户端人工核对并批准 → 回工具核销', padding=(18,12)).pack(fill='x')
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill='both', expand=True, padx=10)
        self.panels = {}
        for group in ('A','B'):
            panel = GroupPanel(self.tabs, store, group)
            self.tabs.add(panel, text=f'   {group} 群   ')
            self.panels[group] = panel
        self.tabs.bind('<<NotebookTabChanged>>', self.tab_changed)
        footer = ttk.Frame(root, padding=(18,8))
        footer.pack(fill='x')
        ttk.Label(footer, text=f'本地数据：{store.directory}', wraplength=1000).pack(side='left')
        ttk.Button(footer, text='使用说明', command=self.help).pack(side='right')
        self.timer = root.after(15000, self.tick)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def tab_changed(self, _=None):
        for panel in self.panels.values():
            panel.on_leave()

    def tick(self):
        try:
            for panel in self.panels.values():
                panel.refresh()
        except (OSError, sqlite3.Error, RuleError) as error:
            messagebox.showerror('刷新失败', str(error), parent=self.root)
        self.timer = self.root.after(15000, self.tick)

    def help(self):
        messagebox.showinfo('使用说明', '1. 先选 A 群或 B 群，填写申请人和 QQ 号并发放。\n2. 人工将口令交给对应 QQ 申请者。\n3. 在当前群输入/选择 QQ 与口令，核验不消耗。\n4. 去 QQ 客户端核对申请者并人工批准。\n5. 回本工具勾选已批准，确认核销。\n\n口令 24 小时有效；过期、撤销、已核销均拒绝。\n群间数据库、表单、筛选、导出独立。\n此工具无法得知 QQ 是否实际批准，由管理员负责确认。\n关闭工具后可复制整个 data 文件夹备份；不提供自动联网或同步。', parent=self.root)

    def close(self):
        self.root.after_cancel(self.timer)
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='QQ群入群口令管理器（完全离线）')
    parser.add_argument('--data-dir', type=Path, help='指定本地数据目录')
    parser.add_argument('--self-test', action='store_true', help='运行隔离的真实 Tk 界面自动检查')
    parser.add_argument('--report', type=Path, help='自检 JSON 报告路径')
    args = parser.parse_args()
    if args.self_test:
        from smoke import run
        try:
            if args.report is None:
                parser.error('--self-test 必须指定 --report')
            report = run(args.report.resolve())
            if sys.stdout is not None:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        except Exception as error:
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), encoding='utf-8')
            return 1
    prepare_tk()
    root = tk.Tk()
    root.withdraw()
    try:
        store = Store(args.data_dir or default_directory())
        App(root, store)
    except (OSError, sqlite3.Error, RuleError) as error:
        messagebox.showerror('启动失败', str(error), parent=root)
        root.destroy()
        return 1
    root.deiconify()
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
