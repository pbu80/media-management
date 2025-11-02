#!/usr/bin/env bash
set -euo pipefail

show_usage() {
  cat <<USAGE
Usage: $(basename "$0") /path/to/movie_folder [output_directory]

The movie_folder should contain the dumped DVD structure (e.g. VIDEO_TS).
The script will create an MKV named after the movie folder.
USAGE
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  show_usage
  exit 1
fi

INPUT_DIR=$(realpath "$1")
if [[ ! -d "$INPUT_DIR" ]]; then
  echo "Input directory not found: $INPUT_DIR" >&2
  exit 1
fi

MOVIE_NAME=$(basename "$INPUT_DIR")
VIDEO_DIR="$INPUT_DIR"
if [[ -d "$INPUT_DIR/VIDEO_TS" ]]; then
  VIDEO_DIR="$INPUT_DIR/VIDEO_TS"
fi

# Gather VOB files that hold actual title data (ignore *_0.VOB menu files)
declare -A group_sizes
declare -A group_lists
while IFS= read -r -d '' file; do
  basename=$(basename "$file")
  # Skip menu or non-title VOBs
  if [[ $basename =~ ^VTS_[0-9]{2}_0\.VOB$ ]]; then
    continue
  fi
  prefix=${basename%_*}
  size=$(stat -c%s "$file")
  group_sizes[$prefix]=$(( ${group_sizes[$prefix]:-0} + size ))
  group_lists[$prefix]+="$file"$'\n'
done < <(find "$VIDEO_DIR" -maxdepth 1 -type f -name 'VTS_[0-9][0-9]_[0-9].VOB' -print0)

if [[ ${#group_sizes[@]} -eq 0 ]]; then
  echo "No title VOB files found in $VIDEO_DIR" >&2
  exit 1
fi

# Select the VTS set with the largest total size (typically the main feature)
best_prefix=""
max_size=0
for prefix in "${!group_sizes[@]}"; do
  size=${group_sizes[$prefix]}
  if (( size > max_size )); then
    max_size=$size
    best_prefix=$prefix
  fi
done

if [[ -z "$best_prefix" ]]; then
  echo "Failed to determine the main title set." >&2
  exit 1
fi

# Prepare the concat list for the best title set
mapfile -t title_files < <(printf '%s' "${group_lists[$best_prefix]}" | sed '/^$/d' | sort)
if [[ ${#title_files[@]} -eq 0 ]]; then
  echo "No VOB files found for title set $best_prefix" >&2
  exit 1
fi

concat_list=$(mktemp)
trap 'rm -f "$concat_list"' EXIT
for file in "${title_files[@]}"; do
  printf "file '%s'\n" "$file" >> "$concat_list"
done

OUTPUT_DIR=${2:-$(dirname "$INPUT_DIR")}
mkdir -p "$OUTPUT_DIR"
OUTPUT_FILE="$OUTPUT_DIR/${MOVIE_NAME}.mkv"

if [[ -f "$OUTPUT_FILE" ]]; then
  echo "Output file already exists: $OUTPUT_FILE" >&2
  exit 1
fi

echo "Converting $MOVIE_NAME using title set $best_prefix..."
ffmpeg -hide_banner -loglevel info -f concat -safe 0 -i "$concat_list" -map 0 -c copy "$OUTPUT_FILE"

echo "Created $OUTPUT_FILE"
