#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [DVD_FOLDER] [OUTPUT_FILE]

Convert a VIDEO_TS DVD folder into an MP4 using ffmpeg while preserving the
original video geometry and audio layout.  When DVD_FOLDER is omitted the
script searches the current directory for a folder containing a VIDEO_TS
subdirectory and uses the first match.

Examples:
  $(basename "$0") /path/to/MyMovie
  $(basename "$0") /path/to/MyMovie /output/MyMovie.mp4
USAGE
}

require_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required tool '$1' not found in PATH" >&2
    exit 1
  fi
}

find_dvd_folder() {
  local search_root="$1"
  local match
  while IFS= read -r -d '' match; do
    echo "$(dirname "$match")"
    return 0
  done < <(find "$search_root" -type d -name VIDEO_TS -print0)
  return 1
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

require_tool ffmpeg
require_tool ffprobe

dvd_folder="${1:-}"
if [[ -z "$dvd_folder" ]]; then
  if ! dvd_folder=$(find_dvd_folder "."); then
    echo "Error: unable to locate a DVD folder containing VIDEO_TS" >&2
    exit 1
  fi
  echo "Auto-detected DVD folder: $dvd_folder"
fi

if [[ ! -d "$dvd_folder" ]]; then
  echo "Error: '$dvd_folder' is not a directory" >&2
  exit 1
fi

video_ts_dir="$dvd_folder/VIDEO_TS"
if [[ ! -d "$video_ts_dir" ]]; then
  echo "Error: '$dvd_folder' does not contain a VIDEO_TS directory" >&2
  exit 1
fi

output_file="${2:-}"
if [[ -z "$output_file" ]]; then
  base_name="$(basename "$dvd_folder")"
  parent_dir="$(dirname "$dvd_folder")"
  output_file="${parent_dir}/${base_name}.mp4"
fi

if [[ -e "$output_file" ]]; then
  echo "Error: output file '$output_file' already exists" >&2
  exit 1
fi

shopt -s nullglob
declare -A title_sizes
for vob in "$video_ts_dir"/VTS_??_*.VOB; do
  [[ -f "$vob" ]] || continue
  base_vob="$(basename "$vob")"
  title="${base_vob%%_*}"
  size=$(stat -c %s "$vob")
  title_sizes[$title]=$(( ${title_sizes[$title]:-0} + size ))
done
shopt -u nullglob

if [[ ${#title_sizes[@]} -eq 0 ]]; then
  echo "Error: no VOB files found in $video_ts_dir" >&2
  exit 1
fi

main_title=""
main_size=0
for title in "${!title_sizes[@]}"; do
  size=${title_sizes[$title]}
  if (( size > main_size )); then
    main_title="$title"
    main_size=$size
  fi
done

if [[ -z "$main_title" ]]; then
  echo "Error: unable to determine main title" >&2
  exit 1
fi

mapfile -t title_files < <(find "$video_ts_dir" -maxdepth 1 -type f -name "${main_title}_*.VOB" | sort -V)
filtered_title_files=()
for file in "${title_files[@]}"; do
  # Skip menu VOBs that end with _0.VOB – they rarely contain main feature audio
  if [[ "$file" =~ _0\.VOB$ ]]; then
    continue
  fi
  filtered_title_files+=("$file")
done

title_files=("${filtered_title_files[@]}")

if [[ ${#title_files[@]} -eq 0 ]]; then
  echo "Error: no segments found for title $main_title" >&2
  exit 1
fi

first_segment="${title_files[0]}"
if [[ ! -f "$first_segment" ]]; then
  echo "Error: first segment $first_segment not found" >&2
  exit 1
fi

mapfile -t video_props < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$first_segment")
width="${video_props[0]:-}"
height="${video_props[1]:-}"
frame_rate="${video_props[2]:-}"

detect_audio_props() {
  local file key value
  for file in "${title_files[@]}"; do
    audio_channels=""
    audio_rate=""
    while IFS='=' read -r key value; do
      case "$key" in
        channels)
          audio_channels="$value"
          ;;
        sample_rate)
          audio_rate="$value"
          ;;
      esac
      if [[ -n "$audio_channels" && -n "$audio_rate" ]]; then
        break
      fi
    done < <(ffprobe -v error -select_streams a:0 -show_entries stream=channels,sample_rate -of default=noprint_wrappers=1 "$file" 2>/dev/null) || true

    if [[ -n "$audio_channels" || -n "$audio_rate" ]]; then
      return 0
    fi
  done
  audio_channels=""
  audio_rate=""
}

detect_audio_props

printf 'Main title detected: %s (%d MB)\n' "$main_title" $(( main_size / 1024 / 1024 ))
echo "Video settings: ${width:-unknown}x${height:-unknown} @ ${frame_rate:-unknown}"
if [[ -n "$audio_channels" || -n "$audio_rate" ]]; then
  echo "Audio settings: channels=${audio_channels:-unknown} sample_rate=${audio_rate:-unknown}"
else
  echo "Audio track not detected; continuing without audio"
fi

temp_list=$(mktemp)
cleanup() {
  rm -f "$temp_list"
}
trap cleanup EXIT

>"$temp_list"
for file in "${title_files[@]}"; do
  printf "file '%s'\n" "$file" >> "$temp_list"
done

echo "Writing output to $output_file"

ffmpeg_cmd=(ffmpeg -hide_banner -loglevel info -f concat -safe 0 -i "$temp_list" -map 0:v:0)

if [[ -n "$audio_channels" ]]; then
  ffmpeg_cmd+=(-map 0:a:0)
fi

ffmpeg_cmd+=(-c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p)

if [[ -n "$frame_rate" ]]; then
  ffmpeg_cmd+=(-r "$frame_rate")
fi

if [[ -n "$audio_channels" ]]; then
  ffmpeg_cmd+=(-c:a aac -b:a 192k -ac "$audio_channels")
fi

if [[ -n "$audio_rate" ]]; then
  ffmpeg_cmd+=(-ar "$audio_rate")
fi

ffmpeg_cmd+=("$output_file")

printf 'Running: '
printf '%q ' "${ffmpeg_cmd[@]}"
printf '\n'

"${ffmpeg_cmd[@]}"

echo "Conversion finished successfully."
