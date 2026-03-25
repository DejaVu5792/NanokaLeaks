run:
    uv run main.py
build:
    uv run nuitka --standalone --onefile --enable-plugin=pyqt6 -o NanokaLeaks main.py
