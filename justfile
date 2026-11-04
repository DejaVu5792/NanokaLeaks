run:
    uv run main.py

# Nuitka caches C objects and the onefile payload in ~/.cache/Nuitka, so
# installing ccache makes repeat builds substantially faster.
build:
    #!/usr/bin/env bash
    set -euo pipefail

    source packaging/nuitka_flags.sh

    uv run nuitka \
        --standalone \
        --onefile \
        --onefile-as-archive \
        "${nuitka_flags[@]}" \
        -o NanokaLeaks \
        main.py

# Build a standalone AppImage under dist/. Downloads appimagetool on first use.
appimage:
    packaging/build_appimage.sh

# Profile a fixed navigation workload on the current branch, then on main.
# Results are written to profiles/ as <branch>.prof, <branch>.txt and
# <branch>.json, and the two JSON summaries are compared at the end.
# Override PROFILE_BASE, PROFILE_WIDTH, PROFILE_HEIGHT, PROFILE_STEP_MS,
# PROFILE_RUNS (median of N passes, default 3) or PROFILE_WARMUP=0 to skip the
# cache-warming pass.
profile:
    #!/usr/bin/env bash
    set -euo pipefail

    root="{{ justfile_directory() }}"
    cd "$root"

    python_bin="$root/.venv/bin/python"
    if [[ ! -x "$python_bin" ]]; then
        echo "error: $python_bin is missing; run 'uv sync' first" >&2
        exit 1
    fi

    base_branch="${PROFILE_BASE:-main}"
    branch="$(git rev-parse --abbrev-ref HEAD)"
    current_commit="$(git rev-parse --short HEAD)"
    base_commit="$(git rev-parse --short "$base_branch")"

    sanitize() {
        printf '%s' "$1" | sed -E 's/[^A-Za-z0-9._-]+/-/g; s/^-+//; s/-+$//'
    }

    current_label="$(sanitize "$branch")"
    base_label="$(sanitize "$base_branch")"
    profiles_dir="${PROFILES_DIR:-$root/profiles}"

    seed_cache="${NANOKA_PROFILE_CACHE:-$HOME/.cache/nanoka_leaks}"
    work_root="$(mktemp -d "${TMPDIR:-/tmp}/nanokaleaks-profile.XXXXXX")"
    worktree=""
    cleanup() {
        if [[ -n "$worktree" ]]; then
            git worktree remove --force "$worktree" >/dev/null 2>&1 || true
        fi
        rm -rf "$work_root"
    }
    trap cleanup EXIT

    invoke_driver() {
        local branch_name="$1" commit="$2" source_root="$3"
        local config_root="$4" cache_root="$5" out_dir="$6" repetitions="$7"

        (
            cd "$source_root"
            XDG_CONFIG_HOME="$config_root" \
            XDG_CACHE_HOME="$cache_root" \
            PYTHONPATH="$source_root${PYTHONPATH:+:$PYTHONPATH}" \
            "$python_bin" "$source_root/tools/profile_navigation.py" \
                --branch "$branch_name" \
                --commit "$commit" \
                --output-dir "$out_dir" \
                --width "${PROFILE_WIDTH:-1280}" \
                --height "${PROFILE_HEIGHT:-900}" \
                --step-ms "${PROFILE_STEP_MS:-8}" \
                --repetitions "$repetitions"
        )
    }

    run_profile() {
        local branch_name="$1" commit="$2" source_root="$3" label="$4"
        local run_root="$work_root/$label"
        local config_root="$run_root/config"
        local cache_root="$run_root/cache"

        mkdir -p "$config_root/nanoka_leaks" "$cache_root"
        if [[ -d "$seed_cache" ]]; then
            echo "Seeding $label cache from $seed_cache"
            cp -a --reflink=auto "$seed_cache" "$cache_root/nanoka_leaks"
        else
            echo "warning: $seed_cache is missing; $label will fetch everything" >&2
            mkdir -p "$cache_root/nanoka_leaks"
        fi

        # Pin the display order and enable every game so both revisions start
        # from exactly the same settings.  The branch's own settings file is
        # never touched.
        cat > "$config_root/nanoka_leaks/settings.json" <<'JSON'
    {
      "cache_character_details": true,
      "cache_character_builds": true,
      "cache_character_artwork": true,
      "sr_centroid_centering": true,
      "game_order": ["zzz", "hsr", "gi", "ww", "nte"],
      "disabled_games": []
    }
    JSON

        # First pass fills the cache for this branch's copy: details, art and
        # every portrait the workload scrolls past.  The measured pass then
        # compares rendering/layout instead of network jitter.
        if [[ "${PROFILE_WARMUP:-1}" == "1" ]]; then
            echo "Warming $label cache (first pass)"
            if ! invoke_driver "$branch_name" "$commit" "$source_root" \
                    "$config_root" "$cache_root" "$run_root/warmup" 1 \
                    >"$run_root/warmup.log" 2>&1; then
                echo "warning: warm-up pass failed for $label" >&2
                tail -30 "$run_root/warmup.log" >&2
                exit 1
            fi
        fi

        local runs="${PROFILE_RUNS:-3}"
        echo "Profiling $branch_name ($commit), $runs measured passes"
        invoke_driver "$branch_name" "$commit" "$source_root" \
            "$config_root" "$cache_root" "$profiles_dir" "$runs"
    }

    run_profile "$branch" "$current_commit" "$root" "$current_label"

    if [[ "$base_label" != "$current_label" ]]; then
        worktree="$work_root/worktree-$base_label"
        git worktree add --detach "$worktree" "$base_branch"
        mkdir -p "$worktree/tools"
        cp "$root/tools/profile_navigation.py" "$worktree/tools/profile_navigation.py"
        run_profile "$base_branch" "$base_commit" "$worktree" "$base_label"
    fi

    echo
    if [[ "$base_label" != "$current_label" ]]; then
        "$python_bin" "$root/tools/compare_profiles.py" \
            "$profiles_dir/$base_label.json" \
            "$profiles_dir/$current_label.json"
    fi

test:
    uv run python -m unittest discover -s tests

# qmllint over every shipped QML source (also run as a unittest).
lint:
    uv run pyside6-qmllint $(find nanoka_viewer/qml -name '*.qml')
