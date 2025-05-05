import os
import platform

def imprimir(path):
    if platform.system() == "Windows":
        os.startfile(path, "print")
    else:
        os.system(f"lp {path}")
