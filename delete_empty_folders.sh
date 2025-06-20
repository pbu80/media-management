#!/bin/bash

# Define the directory path argument
DIRECTORY="$1"

# Define the switch "--force" argument
FORCE="$2"

# Find all empty directories and delete them
find "$DIRECTORY" -type d -empty -delete

# Check if the switch "--force" is provided
if [[ "$FORCE" == "--force" ]]; then
    # Find all directories with a size less than 5MB and delete them
    find "$DIRECTORY" -depth -type d -not -empty -size -5M -delete
else
    # Print a message indicating that the second function will not run
    echo "Warning: The second function will not run without the switch '--force'."
fi
