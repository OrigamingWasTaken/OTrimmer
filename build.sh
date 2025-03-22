python -m venv venv
source ./venv/bin/activate
pip install PyQt5 nuitka
nuitka ./src/otrimmer.py --onefile --enable-plugin=pyqt5 --include-data-files=src/otrimmer.qml=otrimmer.qml --include-data-files=src/gallery.qml=gallery.qml