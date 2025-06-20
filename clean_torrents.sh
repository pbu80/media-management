#!/bin/bash

PREFIXFOLDER="processed"
PATTERN='\[[^]]+\]'
REPLACEMENT_PREFIX="{edition-"
REPLACEMENT_SUFFIX="}"

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

# Function to replace language codes
replace_language_codes() {
  local input="$1"
  input=$(echo "$input" | sed -E 's/\bTam\b/Tamil/g')
  input=$(echo "$input" | sed -E 's/\bTel\b/Telugu/g')
  input=$(echo "$input" | sed -E 's/\bHin\b/Hindi/g')
  input=$(echo "$input" | sed -E 's/\bKan\b/Kannada/g')
  input=$(echo "$input" | sed -E 's/\bMal\b/Malayalam/g')
  input=$(echo "$input" | sed -E 's/\bKoi\b/Korean/g')
  input=$(echo "$input" | sed -E 's/\bEng\b/English/g')
  input=$(echo "$input" | sed -E 's/\bRus\b/Russian/g')
  input=$(echo "$input" | sed -E 's/\bChi\b/Chinese/g')
  input=$(echo "$input" | sed -E 's/\bCzech\b/Czech/g')
  input=$(echo "$input" | sed -E 's/\bSpa\b/Spanish/g')
  input=$(echo "$input" | sed -E 's/\bDan\b/Danish/g')
  echo "$input"
}

# Function to process name (for both files and folders)
process_name() {
  local name="$1"
  # Remove prefix if it starts with "www"
  name=$(echo "$name" | sed 's/^www[^-]*- //')
  if [[ "$name" =~ $PATTERN ]]; then
    LANGUAGES=$(echo "$name" | grep -o -E "$PATTERN" | sed 's/^\[//;s/\]$//')
    REPLACED_LANGUAGES=$(replace_language_codes "$LANGUAGES")
    name=$(echo "$name" | sed "s/\[$LANGUAGES\]/${REPLACEMENT_PREFIX}${REPLACED_LANGUAGES}${REPLACEMENT_SUFFIX}/")
  fi
  echo "$name"
}

# Process folders and files
process_dir() {
  local dir="$1"
  local target_dir="$2"
  
  for item in "$dir"/*; do
    # Skip the target directory to prevent nested "processed" folders
    if [ "$(basename "$item")" == "$PREFIXFOLDER" ]; then
      continue
    fi

    if [[ -d "$item" ]]; then
      # Process folder
      folder_name=$(basename "$item")
      if [[ "$folder_name" == www* ]]; then
        new_folder_name=$(process_name "$folder_name")
        mkdir -p "${target_dir}/${new_folder_name}"
        process_dir "$item" "${target_dir}/${new_folder_name}"
      else
        mkdir -p "${target_dir}/${folder_name}"
        process_dir "$item" "${target_dir}/${folder_name}"
      fi
    elif [[ -f "$item" ]]; then
      # Process file
      file_name=$(basename "$item")
      if [[ "$file_name" == www* ]]; then
        new_file_name=$(process_name "$file_name")
        mv "$item" "${target_dir}/${new_file_name}"
        echo "Moved and renamed: $item -> ${target_dir}/${new_file_name}"
      else
        mv "$item" "${target_dir}/${file_name}"
        echo "Moved: $item -> ${target_dir}/${file_name}"
      fi
    fi
  done
}

# Start processing from MEDIA_DIR
process_dir "$MEDIA_DIR" "${MEDIA_DIR}/${PREFIXFOLDER}"

# Remove empty directories in the source folder
find "${MEDIA_DIR}" -type d -empty -delete
