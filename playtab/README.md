# PlayTab port of Morrowind GOTY (Xbox data)

This repository is [openmw-web](https://github.com/Virtastic/openmw-web) (GPL-3.0) as built for PlayTab's browser
port of The Elder Scrolls III: Morrowind - Game of the Year Edition from the original Xbox disc. It holds the
engine source exactly as delivered (`X_TESM`), plus the scripts of the port. It holds no game data.

## Changes to openmw-web

- `wasm-build/build-deps.sh`: FFmpeg also decodes Xbox ADPCM (`adpcm_ima_wav`) and WMA (`wmav1`, `wmav2`, `asf`
  demuxer): the Xbox disc's voices and music.
- `openmw/components/misc/resourcehelpers.cpp`: `correctSoundPath` tries `.wav` when a `.mp3` is missing (the Xbox
  ESM names voices `.mp3`, the disc holds `.wav`).
- `deps/shim/ushort_char_traits.h`: MyGUI 3.4.3 needs it with current libc++ (same as `wasm-build/include/mygui_char_traits_fix.h`).
- `play/server.py`: port from the `PORT` environment variable.
- `fsroot/resources/vfs/...`: as staged by `wasm-build/link-openmw.sh` at link time.

## Scripts (`playtab/`)

- `build_deps.sh`, `build_engine.sh`: the build (Emscripten 6.0.11, own cache).
- `bsa_names.py`, `esm_xbox2pc.py`, `make_datafiles.py`, `esm_refs.py`: turn the Xbox disc's data into PC "Data Files"
  (the Xbox BSA keeps only name hashes; the Xbox ESM packs INFO DATA in 8 bytes).
- `pack_data.py`, `site/data-sw.js`: the data as 8 MiB chunks and the service worker that serves them to OpenMW.
- `page/`: the PlayTab page (from PlayTab's own page shell, not included here) that runs OpenMW's page in a frame.
- `icons/`: touch button icons from game-icons.net (Lorc, Delapouite), CC BY 3.0.
