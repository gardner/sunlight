#!/bin/bash

echo "Starting Watchdog Loop..."

while true; do
  echo "Starting ingestion pipeline..."
  uv run scripts/parallel_convert_and_embed.py
  
  EXIT_CODE=$?
  
  # Exit code 0 means the python script successfully finished the entire directory
  if [ $EXIT_CODE -eq 0 ]; then
    echo "Pipeline completed successfully! Exiting watchdog."
    break
  fi
  
  # Any other exit code means a SegFault, Memory Error, or unexpected crash
  echo "Pipeline crashed with exit code $EXIT_CODE."
  echo "The corrupt file has been automatically locked out by the .failed marker."
  echo "Restarting pipeline in 5 seconds..."
  sleep 5
done
