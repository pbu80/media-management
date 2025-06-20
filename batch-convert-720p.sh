#!/bin/bash

# Path to the file containing the paths of files to be processed
path_file="/home/pbu80/logs/imported.txt"

# Path to the script that will process the files
convert_script="/home/pbu80/scripts/convert_720p.sh"

# Log file for processed files
log_file="/home/pbu80/logs/processed_720p.log"

# Read each line (path) in the path_file and process it with the convert_script
while read path; do
    # Call the convert_script with the path as argument
    "$convert_script" "$path"
    # Append the path to the log file
    echo "$path" >> "$log_file"
done < "$path_file"

# Clear the contents of the path_file
> "$path_file"
