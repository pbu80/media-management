#!/bin/bash

# Get the root directory from the first argument
root_dir="$1"

# Check if the root directory exists
if [ ! -d "$root_dir" ]; then
  echo "Error: $root_dir does not exist or is not a directory."
  exit 1
fi

# Function to rename folders
rename_folder() {
  local folder="$1"
  local new_foldername
  new_foldername=$(echo "$folder" | awk -F')' '{print $1")"}')

  # Check if the new folder name is different and rename if necessary
  if [ "$folder" != "$new_foldername" ]; then
    mv "$root_dir/$folder" "$root_dir/$new_foldername"
    echo "Renamed folder $folder to $new_foldername"
  fi
}

# Loop through all mkv and mp4 files in the root directory
for file in "$root_dir"/*.mkv "$root_dir"/*.mp4; do
  # Check if the file exists and is a regular file
  if [ -f "$file" ]; then
    # Extract the filename without extension
    filename=$(basename -- "$file")
    filename="${filename%.*}"
    
    # Extract the portion of the filename up to and including the first closing parenthesis ")"
    foldername=$(echo "$filename" | awk -F')' '{print $1")"}')

    # Create a folder with the extracted portion of the filename
    mkdir -p "$root_dir/$foldername"

    # Move the file into the newly created folder
    mv "$file" "$root_dir/$foldername"
    echo "Moved $file to $root_dir/$foldername"
  fi
done

# Loop through all directories in the root directory
for folder in "$root_dir"/*/; do
  # Remove the trailing slash
  folder="${folder%/}"
  # Get the base name of the folder
  folder=$(basename "$folder")
  
  # Rename the folder
  rename_folder "$folder"
done
