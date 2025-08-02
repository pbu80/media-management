#!/bin/bash

# This script updates audio track language tags to a specified language.
# Usage:
#   mkv_lang_switch.sh /path/to/folder --tamil
#   mkv_lang_switch.sh /path/to/folder --custom "Name" lang ietf

if [ $# -lt 2 ]; then
  echo "Usage: $0 /path/to/folder [--tamil|--hindi|--english|--telugu|--malayalam|--custom Name lang ietf]"
  exit 1
fi

folder="$1"
option="$2"

case "$option" in
  --tamil)
    track_name="Tamil"
    lang="tam"
    lang_ietf="ta"
    ;;
  --hindi)
    track_name="Hindi"
    lang="hin"
    lang_ietf="hi"
    ;;
  --english)
    track_name="English"
    lang="eng"
    lang_ietf="en"
    ;;
  --telugu)
    track_name="Telugu"
    lang="tel"
    lang_ietf="te"
    ;;
  --malayalam)
    track_name="Malayalam"
    lang="mal"
    lang_ietf="ml"
    ;;
  --custom)
    if [ $# -ne 5 ]; then
      echo "Usage: $0 /path/to/folder --custom \"Name\" lang ietf"
      exit 1
    fi
    track_name="$3"
    lang="$4"
    lang_ietf="$5"
    ;;
  *)
    echo "Unknown language option: $option"
    exit 1
    ;;
esac

# Log processed files
processed_file="/home/pbu80/logs/.mkv_language_fixed"
touch "$processed_file"

find "$folder" -type f -name '*.mkv' -print0 | while IFS= read -r -d '' file; do
  echo "Processing $file..."

  # Retrieve all audio track numbers
  audio_tracks=$(mkvmerge -J "$file" 2>/dev/null |
    jq -r '.tracks[] |
      select(.type == "audio") |
      (.id + 1)')

  if [ -n "$audio_tracks" ]; then
    for id in $audio_tracks; do
      mkvpropedit "$file" \
        --edit track:$id \
        --set name="$track_name" \
        --set language=$lang \
        --set language-ietf=$lang_ietf
    done
    echo "$(basename "$file")" >> "$processed_file"
  fi

done
