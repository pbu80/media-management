#!/bin/bash

# This script updates tracks with English language tags to Tamil.
# Usage: mkv_lang_switch.sh /path/to/folder

if [ $# -eq 0 ]; then
  echo "No folder path provided. Please provide a folder path as an argument."
  exit 1
fi

# Log processed files
processed_file="/home/pbu80/logs/.mkv_language_fixed"
touch "$processed_file"

find "$1" -type f -name '*.mkv' -print0 | while IFS= read -r -d '' file; do
  echo "Processing $file..."

  # Retrieve audio track numbers using English language settings
  eng_tracks=$(mkvmerge -J "$file" 2>/dev/null |
    jq -r '.tracks[] |
      select(.type == "audio" and (.properties.language == "eng" or .properties.language_ietf == "en" or .properties.language == "English")) |
      (.id + 1)')

  if [ -n "$eng_tracks" ]; then
    for id in $eng_tracks; do
      mkvpropedit "$file" \
        --edit track:$id \
        --set name="Tamil" \
        --set language=tam \
        --set language-ietf=ta
    done
    echo "$(basename "$file")" >> "$processed_file"
  fi

done
