#!/bin/bash

# Wrapper script for OTrimmer
# Allows opening files, directories, or using a file selector

# Path to the otrimmer executable
OTRIMMER_CMD="otrimmer"

# Check if the command can be found
if ! command -v "$OTRIMMER_CMD" &> /dev/null; then
    echo "Error: Could not find the 'otrimmer' command. Make sure it's installed and in your PATH."
    exit 1
fi

# If a path is provided
if [ $# -eq 1 ]; then
    TARGET_PATH="$1"
    
    # Check if it exists
    if [ ! -e "$TARGET_PATH" ]; then
        echo "Error: Path does not exist: $TARGET_PATH"
        exit 1
    fi
    
    # If it's a directory, open gallery mode
    if [ -d "$TARGET_PATH" ]; then
        cd "$TARGET_PATH" || exit 1
        "$OTRIMMER_CMD" -g
    # If it's a file, open trimmer mode
    elif [ -f "$TARGET_PATH" ]; then
        "$OTRIMMER_CMD" "$TARGET_PATH"
    else
        echo "Error: Path is neither a file nor a directory: $TARGET_PATH"
        exit 1
    fi
# No arguments provided, show file selector
else
    # Use KDialog to display a file selector
    if ! command -v kdialog &> /dev/null; then
        echo "Error: kdialog is not installed. Please install it or provide a file path as an argument."
        exit 1
    fi
    
    # Show file selector dialog
    SELECTED_FILE=$(kdialog --title "Select Video File" --getopenfilename "$HOME" "Video Files (*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv *.m4v *.3gp)")
    
    # Check if a file was selected
    if [ -n "$SELECTED_FILE" ]; then
        "$OTRIMMER_CMD" "$SELECTED_FILE"
    else
        echo "No file selected."
        exit 0
    fi
fi