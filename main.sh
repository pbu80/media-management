#!/bin/bash

# Check if a path was provided as input
if [ -z "$1" ]; then
  echo "Please provide a path as input."
  exit 1
fi
log_file="/home/pbu80/logs/main.log"

# look for rar file and extract them
bash "/home/pbu80/scripts/unrar.sh" "$1" >> "$log_file" 2>&1

# clean the mkv files
bash "/home/pbu80/scripts/mkvclean.v3.sh" "$1" >> "$log_file" 2>&1

#trim the video by 1 min
#bash "/home/pbu80/scripts/trimvideo.sh" "$1" >> "$log_file" 2>&1

#Find and clean subs
python3 /home/pbu80/scripts/subcleaner/subcleaner.py "$1" >> "$log_file" 2>&1




