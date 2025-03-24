#!/bin/bash
# package-linker.sh - Link or unlink jutil to the latest Python site-packages directory

# Usage information
usage() {
    echo "Usage: $0 [link|unlink]"
    echo "  link   - Create a symlink from jutil package directory to Python's package directory"
    echo "  unlink - Remove the symlink"
    exit 1
}

# Find the location of this script
SCRIPT_PATH="$(readlink -f "$0")"
HERE_PATH="$(dirname "$SCRIPT_PATH")"

# Setup package name and source paths
PACKAGE_NAME="jutil"
PACKAGE_SOURCE_PATH="$HERE_PATH/$PACKAGE_NAME"

# Make sure the source path exists
if [ ! -d "$PACKAGE_SOURCE_PATH" ]; then
    echo "Error: PACKAGE_SOURCE_PATH directory does not exist: $PACKAGE_SOURCE_PATH"
    exit 1
fi

# Check command argument
if [ $# -ne 1 ] || [[ ! "$1" =~ ^(link|unlink)$ ]]; then
    usage
fi
COMMAND="$1"

# Find the latest Python version directory
LATEST_PYTHON_DIR=$(ls -d /usr/local/lib/python3.* 2>/dev/null | sort -V | tail -n 1)

# Check if a Python directory was found
if [ -z "$LATEST_PYTHON_DIR" ]; then
    echo "Error: No Python directories found in /usr/local/lib/"
    exit 1
fi

# Check if dist-packages or site-packages exists (different distros use different names)
if [ -d "$LATEST_PYTHON_DIR/dist-packages" ]; then
    TARGET_DIR="$LATEST_PYTHON_DIR/dist-packages"
elif [ -d "$LATEST_PYTHON_DIR/site-packages" ]; then
    TARGET_DIR="$LATEST_PYTHON_DIR/site-packages"
else
    echo "Error: No dist-packages or site-packages directory found in $LATEST_PYTHON_DIR"
    exit 1
fi

# Perform the requested action
if [ "$COMMAND" = "link" ]; then
    # Create the symlink
    sudo ln -sf "$PACKAGE_SOURCE_PATH" "$TARGET_DIR/$PACKAGE_NAME"
    echo "Linked $PACKAGE_SOURCE_PATH to $TARGET_DIR/$PACKAGE_NAME"
    echo "Python version: $(basename $LATEST_PYTHON_DIR)"
else
    # Check if the symlink exists
    if [ ! -L "$TARGET_DIR/$PACKAGE_NAME" ]; then
        echo "Error: Symlink $TARGET_DIR/$PACKAGE_NAME does not exist"
        exit 1
    fi

    # Remove the symlink
    sudo rm "$TARGET_DIR/$PACKAGE_NAME"
    echo "Removed symlink from $TARGET_DIR/$PACKAGE_NAME"
fi


## Cheap Way to Fully Install ###############################
# set -e
# sudo mkdir -p /usr/lib/python3/dist-packages/jlutil/jlutil
# sudo rsync \
#     -av \
#     --delete \
#     --exclude='*.sh' \
#     --exclude='__pycache__' \
#     --exclude '*.pyc' \
#     ./jlutil/. \
#     /usr/lib/python3/dist-packages/jlutil/.
