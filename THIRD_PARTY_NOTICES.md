# 第三方协议与署名

自有应用代码：MIT，见根目录 LICENSE。第三方协议全文收录于 `third_party_licenses/`，版本与来源见其中 `INDEX.json`。

运行依赖：Python 解释器及其标准库（PSF 及 Python LICENSE 中列出的第三方条款）、Tcl/Tk（保留各自版权与许可）。Windows EXE 含 Python/Tcl/Tk 运行时；Python 的内置组件许可不因本项目 MIT 改变。

构建依赖：PyInstaller（GPL 2.0 或以后版本并带 bootloader 分发例外；全文含例外）、altgraph、packaging、pefile、pywin32-ctypes、pyinstaller-hooks-contrib、setuptools。开发工具许可随原文件保留，不将 GPL 或例外改写成 MIT。附带 Python 环境中构建工具的许可证是保守保留，并不表示其全部代码均进入 EXE。

本项目不分发 FFmpeg/ffprobe、HandBrake、浏览器或视频编码器。它们是用户可选的独立软件；须按实际取得版本的原协议使用或再分发。现有 EXE 构建不捆绑 ffprobe。没有把视频编码器的商标、专利或许可权授予用户。

许可证版本清单描述 2026-11-02 本机构建环境。CI 的 Python 来自 GitHub 托管环境，实际补丁版本和所含 Tcl/Tk 以 CI 构建日志为准；没有声称二进制可逐字节重现。
