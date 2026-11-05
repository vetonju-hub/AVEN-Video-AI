import sys
import traceback
from pathlib import Path
from aven.runtime import user_root


def main():
    if '--self-test' in sys.argv:
        from aven.selftest import self_test
        self_test(Path(sys.argv[sys.argv.index('--self-test')+1])); return
    import tkinter as tk
    from aven.app import Studio
    root=tk.Tk(); studio=Studio(root)
    if '--gui-smoke' in sys.argv:
        from aven.selftest import gui_smoke
        gui_smoke(root,studio)
        root.destroy(); return
    root.mainloop()


if __name__=='__main__':
    try: main()
    except Exception:
        log=user_root()/'app-error.log'; log.parent.mkdir(parents=True,exist_ok=True)
        log.write_text(traceback.format_exc(),encoding='utf-8')
        if '--self-test' in sys.argv or '--gui-smoke' in sys.argv: sys.exit(1)
        if getattr(sys,'frozen',False):
            import ctypes
            from aven.i18n import Locale,message
            text=Locale(user_root()/'settings.json').render(message('AVEN konnte nicht starten. Details: {path}',path=str(log)))
            ctypes.windll.user32.MessageBoxW(0,text,'AVEN Video AI',16)
        raise
