#!/bin/bash

if [ $# -ne 1 ]; then
  echo "Usage: $0 <mkv-file>"
  exit 1
fi

if ! command -v mkvextract &> /dev/null; then
  echo "mkvextract not found. Please install the mkvtoolnix package."
  exit 1
fi

input_file="$1"
output_dir="$(dirname "$input_file")"
output_file="${input_file%.mkv}-nosubs.mkv"
for track in $(mkvmerge -i "$input_file" | grep 'subtitles' | awk -F: '{print $1}'); do
  filename=$(basename "$input_file" .mkv | sed 's/-$//')
  language=$(mkvinfo "$input_file" | grep -A 1 "Track number: $track" | grep "Language" | awk -F: '{print $2}' | sed 's/^ //' | tr '[:upper:]' '[:lower:]')
  if [ "$language" = "eng" ]; then
    suffix=".eng"
    subtitle_file="$output_dir/$filename.srt"
    mkvextract tracks "$input_file" "$track:$subtitle_file"

  else
    suffix=".eng"
  fi
  subtitle_file="$output_dir/$filename.srt"
  mkvextract tracks "$input_file" "$track:$subtitle_file"
  mkvmerge -o "$output_file" --no-subtitles "$input_file"
  python3 /home/pbu80/scripts/subcleaner/subcleaner.py "$output_dir/$filenamesrt" 
 
done
mkvmerge -o "$output_file" --no-subtitles "$input_file"
rm "$input_file"
echo "Subtitles extracted to $output_dir."


