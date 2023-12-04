#!/bin/bash
HUB=lucid-hub-acmm
DEVICE="2105-NS32-1001-ABD4"
DIR="/home/rabryan/Documents/lucid/experiments/c2c12-imaging/2023-10-27-coarse-interleave/"
while true; do
    echo "Pausing"
    ssh lucid@$HUB ldmc devices exec $DEVICE Pause-Extend
    echo "Sleeping 4 minutes..."
    sleep 240
    echo "Capturing Images"
    python3 pycm30/cli.py scan-32x-ss $DIR --hostname $HUB
    echo "Resuming Operation"
    ssh lucid@$HUB ldmc devices exec $DEVICE Resume-Operation
    echo "Sleeping 4 hours..."
    sleep 14400
done
