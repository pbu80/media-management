#!/bin/bash
find ~/Stuff/local/Foreign/ -type f -name "*.srt" -exec grep -lZ 'YTS' {} + | xargs -0 -I {} python ~/scripts/subcleaner/subcleaner.py "{}"
