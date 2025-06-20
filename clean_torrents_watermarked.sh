#!/bin/bash

PREFIXFOLDER="processed"
WATERMARK="{edition- Watermarked}"

# Check if the path argument is provided
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 path/to/media/files"
  exit 1
fi

# Define the directory where media files are located
MEDIA_DIR="$1"

# Create the target directory if it doesn't exist
if [[ ! -d "${MEDIA_DIR}/${PREFIXFOLDER}" ]]; then
  mkdir "${MEDIA_DIR}/${PREFIXFOLDER}"
fi

# Function to process file names:
# Removes "www" prefix (if any) and appends the watermark.
process_file_name() {
  local filename="$1"
  # Remove any prefix that starts with "www"
  filename=$(echo "$filename" | sed 's/^www[^-]*- //')
  # Append watermark before file extension if it exists
  if [[ "$filename" == *.* ]]; then
    local base="${filename%.*}"
    local ext="${filename##*.}"
    echo "${base}${WATERMARK}.${ext}"
  else
    echo "${filename}${WATERMARK}"
  fi
}

# Function to process folder names:
# Only removes the "www" prefix if it exists.
process_folder_name() {
  local foldername="$1"
  echo "$(echo "$foldername" | sed 's/^www[^-]*- //')"
}

# Process folders and files recursively
process_dir() {
  local dir="$1"
  local target_dir="$2"
  
  for item in "$dir"/*; do
    # Skip the target directory to prevent nested "processed" folders
    if [ "$(basename "$item")" == "$PREFIXFOLDER" ]; then
      continue
    fi

    if [[ -d "$item" ]]; then
      # For directories, remove "www" prefix if present
      folder_name=$(basename "$item")
      if [[ "$folder_name" == www* ]]; then
        new_folder_name=$(process_folder_name "$folder_name")
      else
        new_folder_name="$folder_name"
      fi
      mkdir -p "${target_dir}/${new_folder_name}"
      process_dir "$item" "${target_dir}/${new_folder_name}"
    elif [[ -f "$item" ]]; then
      # For files, remove "www" prefix and append watermark
      file_name=$(basename "$item")
      new_file_name=$(process_file_name "$file_name")
      mv "$item" "${target_dir}/${new_file_name}"
      echo "Moved and watermarked: $item -> ${target_dir}/${new_file_name}"
    fi
  done
}

# Start processing from the specified media directory
process_dir "$MEDIA_DIR" "${MEDIA_DIR}/${PREFIXFOLDER}"

# Remove empty directories in the source folder
find "${MEDIA_DIR}" -type d -empty -delete
