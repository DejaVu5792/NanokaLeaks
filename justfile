run:
    uv run main.py

# Nuitka caches C objects and the onefile payload in ~/.cache/Nuitka, so
# installing ccache makes repeat builds substantially faster.
build:
    uv run nuitka --standalone --onefile --onefile-as-archive --enable-plugin=pyside6 --assume-yes-for-downloads -o NanokaLeaks main.py

test:
    uv run python -m unittest discover -s tests
