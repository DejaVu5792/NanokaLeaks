run:
    uv run main.py
build:
    uv run nuitka --standalone --onefile --enable-plugin=pyside6 -o NanokaLeaks main.py
test:
    uv run python -m unittest discover -s tests
