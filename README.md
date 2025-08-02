# Media Management Scripts

This repository contains a collection of small bash utilities used to clean and organise movie files.  Most scripts were written for a personal environment and may reference log files or helper scripts in `/home/pbu80`.  Update the variables at the top of each script to match your paths.

## Requirements

Several scripts depend on external tools:

- **ffmpeg** – used for video/audio conversion.
- **mkvtoolnix** (provides `mkvmerge`, `mkvpropedit`, `mkvinfo`, `mkvextract`).
- **unrar** – used by `main.sh`.
- **Python 3** – required for `subcleaner.py` when called from some scripts.
- Standard GNU utilities (`find`, `xargs`, `rsync`, etc.).

Ensure these programs are installed and available in your `PATH`.

## Configuring Log Paths

Many scripts write to log files located under `/home/pbu80/logs`.  If your environment differs, edit the variables named `log_file`, `path_file` or `processed_file` inside each script and point them to your preferred log directory.  Example:

```bash
# inside ac3_convertion.sh
log_file="/var/log/media/ac3_conversion.log"
```

## Scripts

Below is a short description and example usage for each script in this repository.

### `ac3_convertion.sh`
Converts MKV files containing EAC3 audio to AC3.  Works on a single file or every MKV in a directory and deletes the originals after conversion.

```bash
bash ac3_convertion.sh /path/to/video.mkv
bash ac3_convertion.sh /path/to/folder/
```

### `batch-convert-720p.sh`
Reads paths from `imported.txt`, calls an external `convert_720p.sh` script on each entry and logs processed files.  Edit the variables `path_file`, `convert_script` and `log_file` to suit your system.

```bash
bash batch-convert-720p.sh
```

### `clean_and_move.sh`
Cleans torrent downloads, moves files into individual folders and performs MKV clean‑up.  Takes three arguments: the source directory, the destination directory and a log file.

```bash
bash clean_and_move.sh /downloads/movies /movies/Tamil /var/log/clean.log
```

### `clean_trim_and_move.sh`
Similar to `clean_and_move.sh` but watermarks torrent names and trims the first minute of video before moving.

```bash
bash clean_trim_and_move.sh /downloads/movies /movies/Tamil /var/log/clean.log
```

### `clean_torrents.sh`
Renames files/folders from torrent releases, converting language codes and placing the results in a `processed` subfolder.

```bash
bash clean_torrents.sh /path/to/torrent/folder
```

### `clean_torrents_watermarked.sh`
Variant of `clean_torrents.sh` that appends `{edition- Watermarked}` to file names.

```bash
bash clean_torrents_watermarked.sh /path/to/torrent/folder
```

### `clean_yts_subs.sh`
Runs `subcleaner.py` on subtitle files containing the "YTS" tag within `~/Stuff/local/Foreign/`.

```bash
bash clean_yts_subs.sh
```

### `delete_empty_folders.sh`
Deletes empty directories in the given path.  With `--force` it also removes non‑empty folders smaller than 5 MB.

```bash
bash delete_empty_folders.sh /path/to/root
bash delete_empty_folders.sh /path/to/root --force
```

### `extsubs.sh`
Extracts all subtitle tracks from an MKV and saves them as `.srt` files while creating a new MKV without subtitles.  Requires `mkvextract`, `mkvmerge` and `mkvinfo`.

```bash
bash extsubs.sh movie.mkv
```

### `main.sh`
General processing script that unrars archives, cleans MKV files and runs subtitle cleaning.  Edit the `log_file` path as required.

```bash
bash main.sh /path/to/folder
```

### `mkvclean.v3.sh`
Strips track titles and attachments from all MKVs in a directory and logs processed files to `.mkvcleaned`.

```bash
bash mkvclean.v3.sh /path/to/folder
```

### `movie2folder.sh`
Creates a folder for each MKV/MP4 file based on its name (up to the first closing parenthesis) and moves the file into that folder.

```bash
bash movie2folder.sh /path/to/folder
```

### `mkv_lang_switch.sh`
Updates the language tags for every audio track in MKV files to a specified language.  Supports predefined options such as `--tamil`, `--hindi`, `--english`, `--telugu`, `--malayalam` or a `--custom` name/language/language‑ietf combination.

```bash
bash mkv_lang_switch.sh /path/to/folder --tamil
```

## Notes

Several scripts call helper utilities not present in this repository (e.g. `convert_720p.sh`, `unrar.sh`, `trimvideo.sh`).  Ensure those exist on your system or adjust the scripts accordingly.

