#!/bin/bash

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "FFmpeg is not installed. Please install FFmpeg and try again."
    exit 1
fi

# Check if mkvinfo is installed
if ! command -v mkvinfo &> /dev/null; then
    echo "mkvinfo (MKVToolNix) is not installed. Please install MKVToolNix and try again."
    exit 1
fi

# Function to process a single file
process_file() {
    local file="$1"

    # Check if the input file contains "EAC3" in the audio encoding
    if ! mkvinfo "$file" | grep -q "A_EAC3"; then
        echo "Skipping conversion. Input file audio is not encoded as EAC3: $file"
        return
    fi

    # Set the output file name with the "cvt" suffix
    output_file="${file/EAC3/AC3}"
    output_file="${output_file%.*}_cvt.${output_file##*.}"

    # Check if the input file is already processed (present in the log file), if so, skip the conversion
    if grep -Fxq "$file" "$log_file"; then
        echo "File already processed. Skipping conversion: $file"
        return
    fi

    # Convert the audio from EAC3 to AC3 using FFmpeg
    ffmpeg -i "$file" -c:v copy -c:a ac3 -map 0 "$output_file"

    # Check if conversion was successful
    if [ $? -eq 0 ]; then
        echo "Conversion complete. Output file: $output_file"

        # Add the input filename to the log file
        echo "$file" >> "$log_file"

        # Delete the input file
        rm "$file"
    else
        echo "An error occurred during the conversion: $file"
    fi
}

# Check if input is provided
if [ -z "$1" ]; then
    echo "Please provide the input file or directory as an argument."
    exit 1
fi

# Log file path
log_file="/home/pbu80/logs/ac3_conversion.log"

# Check if the log file exists, if not create a new log file
if [ ! -f "$log_file" ]; then
    touch "$log_file"
fi

# Process the input
if [ -f "$1" ]; then
    # Input is a file
    process_file "$1"
elif [ -d "$1" ]; then
    # Input is a directory
    directory="$1"
    echo "Processing files in directory: $directory"

    # Loop through MKV files in the directory and process them
    for file in "$directory"/*.mkv; do
        [ -e "$file" ] || continue
        process_file "$file"
    done
else
    echo "Input is neither a file nor a directory."
    exit 1
fi
