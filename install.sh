#! /bin/bash

# This is a mediocre way to install, but fine for now

set -e

sudo mkdir -p /usr/lib/python3/dist-packages/jlutil/jlutil
sudo rsync \
    -av \
    --delete \
    --exclude='*.sh' \
    --exclude='__pycache__' \
    --exclude '*.pyc' \
    ./jlutil/. \
    /usr/lib/python3/dist-packages/jlutil/.
