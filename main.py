import sys
from PyQt6 import QtWidgets
from ui.controller import MainController

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainController()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
