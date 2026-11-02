# QQ群入群口令管理器 1.0.0

Windows 11 本地桌面工具，Python tkinter + SQLite。应用完全离线，无机器人、服务器、QQ 协议、联网、遥测、自动发消息或自动批准功能。

## 直接启动

解压整个 ZIP，双击 `run.bat` 或包内 `QQPassManager.exe`。EXE 已包含 Python/Tk 运行时，无需安装 Python。不要在 ZIP 预览里直接运行。

源码版：安装带 tkinter 的 Python 3.10 或以上版本，双击 `run.bat`，或执行 `py -3 app.py`。运行时不需要 pip 安装任何依赖。

默认数据库位置：`%LOCALAPPDATA%\QQPassManager\data`。EXE 升级/移动不会清空旧数据。A 群为 `group_A.sqlite3`，B 群为 `group_B.sqlite3`，不存放在 EXE 的临时解包目录。

需要便携目录时：`QQPassManager.exe --data-dir "D:\我的入群工具\data"`，源码对应 `py -3 app.py --data-dir "D:\我的入群工具\data"`。请始终指定同一目录，换目录会出现另一套空数据库。

## 人工工作流程

1. 选择 **A 群** 或 **B 群**；填写申请人、QQ 号、备注，点击“新建并发放”。QQ 号须为 5–12 位数字且不以 0 开头。表格可选择记录，查看口令和各时间。
2. 人工将口令交给对应 QQ 申请者。复制按钮仅写本机剪贴板，不发送消息。
3. 在对应群输入/选择申请者 QQ 号与 8 位口令，点击“① 核验”。**核验不消耗口令**，可以重复核验。
4. 在 **QQ 官方客户端**人工核对实际申请者 QQ 号、目标群及口令，人工批准入群。
5. 回工具勾选“我已在 QQ 客户端核对并批准”，再点击核销，并确认 QQ 号和群。**必须先人工批准，再核销。**工具无法读取或确认 QQ 中是否真的批准；勾选项是管理员的人工声明。

输入变化或切换群会清除核验凭据与人工确认，需要重新核验。核销时再次原子检查群、QQ、口令、有效期和状态，不依赖界面上旧的“通过”提示。

## 隔离和口令规则

- A/B 群拥有独立 SQLite 文件、申请人、QQ 号绑定、口令历史、状态、备注、表单、搜索与筛选。相同 QQ 可在两群分别申请，互不影响。没有“全部群”查询或导出。
- 口令为 8 位，由 `secrets.choice` 安全随机产生；不含 `0 O 1 I l B 8 S Z`，只含大写字母及部分数字。输入不区分大小写，忽略首尾空格。
- 两群的第一位字符从互不重叠的随机字符池产生，其余 7 位从完整字符池随机产生；没有固定前缀。这样即便 QQ 号相同，口令也绝不可能在两群碰巧重复。本群永久保留历史口令，随机碰撞会重试，不覆盖旧令。
- 发放时起 **24 小时**有效；到达过期秒数即拒绝。以本机系统时间计算，显示本机时区和偏移。界面约每 15 秒刷新，实际核验/核销即时检查。
- 状态为“待核验 / 已核验·未核销 / 已核销 / 已撤销 / 已过期”。已核销、撤销、过期均不能核验通过或核销；重复核销拒绝。两个进程同时核销只允许一次成功。
- 同群同一 QQ 只建一个申请者档案。重复新建拒绝；可编辑姓名/备注，QQ 绑定不可直接修改。填错 QQ 时撤销旧令，再以正确 QQ 新建档案。
- 需重发时选择记录，点击“撤销旧令并重发”，确认后原有效令立即撤销、新令重新计时 24 小时，旧记录保留。已核销申请者禁止重发。不支持删除历史或恢复撤销。
- 姓名/备注属于本群的申请者档案，编辑后该申请者的历史行也显示更新后的姓名/备注；各历史口令和状态不改变。
- 搜索匹配当前群的姓名、QQ、口令、备注，按文字子串匹配；可与状态筛选组合。CSV 仅导出当前群的当前筛选，包含历史匹配行；使用 UTF-8 BOM、标准引号/换行转义，并对可执行表格公式的文本加前导单引号。

## 数据保管与备份

数据库及 CSV 含明文 QQ、口令和备注，方便管理员查询/复制。请使用个人 Windows 账户保存，妥善保管导出文件；此版本没有加密、管理员登录或密码恢复功能。

**备份：**关闭本工具的所有实例，复制整个 `data` 文件夹到另一个本地位置。恢复时同样先关闭所有实例，再将完整备份放回原数据目录。不要交换两群的文件名，群标识不符会拒绝启动；不自动合并不同备份。

工具会保存各群上次成功写入的时间；检测到本机时间倒退时拒绝写入，提示校准时间。纯离线工具没有可信外部时钟：不能防止人工篡改数据库、恢复旧备份、完全控制系统时钟或具有文件访问权限的人。使用时保持 Windows 时间准确。

## 自动测试

双击 `test.bat`，或：

```bat
py -3 -m unittest discover -s tests -v
py -3 app.py --self-test --report ".build\checks\source-selftest.json"
QQPassManager.exe --self-test --report ".build\checks\exe-selftest.json"
```

单元测试使用临时数据库与可控时钟；界面自检创建真实 tkinter 控件、调用按钮和业务回调，用合成数据替代真实申请，弹窗答复与保存路径自动提供。自检数据只写入报告旁的临时目录并清理，不读取默认数据库，不打开 QQ。它验证工具自身流程，**不代表真实 QQ 审核已验收**。无需等满 24 小时：过期边界用注入时钟验证。

`VALIDATION.md` 记录本次归档测试与构建结果。测试环境为 Windows 11 x64；未测试其他 Windows 版本，也没有进行真实群/真实账号操作。

## 构建 Windows EXE

在 Windows 11 x64 安装含 tkinter 的 Python 3.10+，双击 `build.bat`。脚本先检查 Tk、跑单元测试，再调用 PyInstaller 生成单文件窗口程序 `dist\QQPassManager.exe`，最后运行该 EXE 的隔离界面自检（45 秒超时失败）。任一步失败均返回失败，不能当作构建成功。`build_exe.py` 会在构建进程内补充 Conda DLL 搜索路径，兼容基于 Conda 的虚拟环境，不修改系统环境变量。

应用运行完全离线。**仅构建时**若选中 Python 尚未安装 PyInstaller，脚本会在工程内创建 `.venv-build` 并通过 pip 安装 `requirements-build.txt`。若需离线构建，可提前准备 PyInstaller 及其依赖 wheel 文件到一个本地目录，并设置 `QQPASS_WHEELS`；或选用已经安装 PyInstaller 的 Python。

```bat
set "QQPASS_PYTHON=C:\Path To Python\python.exe"
set "QQPASS_WHEELS=D:\offline-wheels"
build.bat
```

`QQPASS_PYTHON` 可覆盖自动寻找的 Python；`QQPASS_NO_PAUSE=1` 可取消批处理结束时暂停，便于自动运行。本次发行使用已安装的 Python/PyInstaller 构建，未下载依赖。包内 EXE 未作代码签名。

## 文件

`app.py` 界面入口；`core.py` 业务与数据库；`tk_startup.py` Windows Tcl 初始化兼容；`smoke.py` 隔离界面自检；`tests/` 单元测试（含跨进程持久化）；`run.bat` 启动；`test.bat` 测试；`build.bat` / `build_exe.py` 构建；`check_exe.py` 成品自检；`find_python.bat` 解释器定位辅助；`requirements-build.txt` 构建依赖。

## GitHub 归档、安装与协议

从本仓库 [Releases](../../releases) 下载 Windows ZIP，完整解压后启动 EXE；Git 的源码 ZIP 不含 EXE。源码运行和本地构建见上文。CI 在 Windows 执行单元测试、隔离界面自检和构建，并保存构建附件；自动检查不代表真实 QQ 审批闭环。

自有源码采用 [MIT](LICENSE)，第三方协议见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。[归档说明](docs/ARCHIVE.md) 与 [本次验证](VALIDATION.md) 说明数据排除和验收边界。
