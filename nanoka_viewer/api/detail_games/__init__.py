"""Per-game detail normalizers.

Each module turns one game's raw character JSON into the shared
:mod:`nanoka_viewer.api.detail_models` objects.  They are deliberately free of
network and cache code: :mod:`nanoka_viewer.api.details` owns loading, this
package owns parsing.
"""
