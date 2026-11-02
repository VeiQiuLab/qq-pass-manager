"""Initialize native Tcl cwd before Tcl_Init on relocated Windows runtimes."""
import sys
from pathlib import Path


def prepare_tk():
    if sys.platform != 'win32':
        return
    import ctypes
    base = Path(getattr(sys, '_MEIPASS', sys.base_prefix))
    for candidate in (base/'tcl86t.dll',base/'DLLs'/'tcl86t.dll',base/'Library'/'bin'/'tcl86t.dll'):
        if not candidate.is_file():
            continue
        dll = ctypes.WinDLL(str(candidate))
        dll.Tcl_CreateInterp.restype = ctypes.c_void_p
        dll.Tcl_Eval.argtypes = (ctypes.c_void_p,ctypes.c_char_p)
        dll.Tcl_DeleteInterp.argtypes = (ctypes.c_void_p,)
        interp = dll.Tcl_CreateInterp()
        try:
            if dll.Tcl_Eval(interp,b'pwd') != 0:
                raise RuntimeError('Tcl 当前路径初始化失败。')
        finally:
            dll.Tcl_DeleteInterp(interp)
        return
