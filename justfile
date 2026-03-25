run:
    uv run main.py
build:
    uv run nuitka --onefile --enable-plugin=pyqt6 main.py
