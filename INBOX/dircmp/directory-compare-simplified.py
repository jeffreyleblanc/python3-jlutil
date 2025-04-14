#! /usr/bin/env python3

import subprocess
import json
import re
from pathlib import Path

def compare_dirs(dir1, dir2, include_permissions=True, bidirectional=True):
    """
    Compare two directories using rsync
    Returns structured data about differences between directories

    Args:
        dir1: Path to first directory
        dir2: Path to second directory
        include_permissions: Whether to include permission differences
        bidirectional: Whether to run rsync in both directions for complete comparison

    Returns:
        Dictionary with comparison results
    """
    # Run comparison in one direction first
    forward_result = compare_dirs_oneway(dir1, dir2, include_permissions)
    
    # If bidirectional is enabled, also run comparison in reverse direction
    if bidirectional:
        reverse_result = compare_dirs_oneway(dir2, dir1, include_permissions)
        # Merge the results (with dir1/dir2 swapped for reverse comparison)
        merged_result = merge_comparison_results(forward_result, reverse_result)
        return merged_result
    else:
        return forward_result

def should_exclude_file(path):
    """
    Check if a file should be excluded from comparison
    
    Args:
        path: The file path to check
        
    Returns:
        bool: True if file should be excluded, False otherwise
    """
    # Exclude symlinks (detected by " -> " in the path)
    if " -> " in path:
        return True
    
    # Exclude files with special characters
    special_chars = "@#$%"
    if any(char in path for char in special_chars):
        return True
    
    return False

def compare_dirs_oneway(dir1, dir2, include_permissions=True):
    """
    Compare two directories using rsync in one direction
    
    Args:
        dir1: Path to first directory
        dir2: Path to second directory
        include_permissions: Whether to include permission differences
        
    Returns:
        Dictionary with comparison results
    """
    # Ensure paths end with a trailing slash for rsync semantics
    if not str(dir1).endswith('/'):
        dir1 = f"{dir1}/"
    if not str(dir2).endswith('/'):
        dir2 = f"{dir2}/"

    # Build rsync command with all the parameters we want
    rsync_cmd = [
        'rsync',
        '--dry-run',  # Simulation mode
        '-i',         # Itemize changes for detailed output
        '-a',         # Archive mode to preserve attributes
        '--delete',   # Consider files that need to be deleted
    ]

    # Add checksum comparison if needed for more accurate file comparison
    if include_permissions:
        rsync_cmd.append('--checksum')

    rsync_cmd.extend([dir1, dir2])

    # Run the rsync command
    proc = subprocess.Popen(
        rsync_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = proc.communicate()

    if proc.returncode != 0 and proc.returncode != 23:  # rsync returns 23 when there are skipped files
        raise Exception(f"rsync failed with error: {stderr}")

    # Parse the output into structured data
    result = {
        "only_in_dir1": [],  # Files in dir1 not in dir2 (would be sent)
        "only_in_dir2": [],  # Files in dir2 not in dir1 (would be deleted with --delete)
        "diff_files": [],    # Files that differ in content
        "diff_attrs": [],    # Files that differ only in attributes (permissions, owner, etc)
        "excluded_files": [], # Files excluded from comparison (symlinks, special chars)
        "summary": {
            "only_in_dir1_count": 0,
            "only_in_dir2_count": 0,
            "diff_files_count": 0,
            "diff_attrs_count": 0,
            "excluded_files_count": 0
        }
    }

    # Parse rsync's itemized output
    for line in stdout.splitlines():
        if not line or line.startswith('sending ') or line.startswith('total '):
            continue

        # The first character of rsync itemized output indicates the update type
        if len(line) < 2:
            continue

        update_type = line[0]
        metadata = line[1:11] if len(line) > 11 else ""
        filename = line[12:] if len(line) > 12 else ""

        # Skip directory entries - just focus on files
        if metadata.startswith('d'):
            continue
            
        # Check if this file should be excluded
        if should_exclude_file(filename):
            # Extract just the base filename without the symlink target
            base_filename = filename.split(" -> ")[0] if " -> " in filename else filename
            reason = "symlink" if " -> " in filename else "special characters"
                
            result["excluded_files"].append({
                "path": base_filename,  # Use normalized path
                "reason": reason
            })
            result["summary"]["excluded_files_count"] += 1
            continue

        # New file (would be copied from dir1 to dir2)
        if update_type == '>':
            result["only_in_dir1"].append({
                "path": filename,
                "type": "file" if not metadata.startswith('d') else "directory"
            })
            result["summary"]["only_in_dir1_count"] += 1

        # Deleted file (would be removed from dir2)
        elif update_type == '*' or update_type == 'c':
            result["only_in_dir2"].append({
                "path": filename,
                "type": "file" if not metadata.startswith('d') else "directory"
            })
            result["summary"]["only_in_dir2_count"] += 1

        # Content differences (would be updated)
        elif update_type == '.':
            # Check if the changes are content or just attributes
            if 's' in metadata:  # Size is different
                result["diff_files"].append({
                    "path": filename,
                    "differences": {
                        "content": True,
                        "size": 's' in metadata,
                        "time": 't' in metadata,
                        "permissions": 'p' in metadata,
                        "owner": 'o' in metadata,
                        "group": 'g' in metadata,
                    }
                })
                result["summary"]["diff_files_count"] += 1
            else:
                # Just attribute changes (permissions, etc.)
                result["diff_attrs"].append({
                    "path": filename,
                    "differences": {
                        "content": False,
                        "time": 't' in metadata,
                        "permissions": 'p' in metadata,
                        "owner": 'o' in metadata,
                        "group": 'g' in metadata,
                    }
                })
                result["summary"]["diff_attrs_count"] += 1

    # Get total file counts - run another command to count files
    dir1_cmd = f"find {dir1} -type f | wc -l"
    dir2_cmd = f"find {dir2} -type f | wc -l"

    try:
        dir1_count = int(subprocess.check_output(dir1_cmd, shell=True).decode().strip())
        dir2_count = int(subprocess.check_output(dir2_cmd, shell=True).decode().strip())

        result["summary"]["dir1_total_files"] = dir1_count
        result["summary"]["dir2_total_files"] = dir2_count

    except (subprocess.SubprocessError, ValueError):
        # If the file count fails, just continue without it
        pass

    return result

def merge_comparison_results(forward_result, reverse_result):
    """
    Merge results from bidirectional comparison
    
    Args:
        forward_result: Result from dir1 -> dir2 comparison
        reverse_result: Result from dir2 -> dir1 comparison
        
    Returns:
        Dictionary with merged comparison results
    """
    # Extract and normalize excluded files from both directions
    excluded_files = {}
    excluded_paths = set()
    
    # Process excluded files from forward comparison
    for item in forward_result.get("excluded_files", []):
        path = item["path"]
        base_path = path.split(" -> ")[0] if " -> " in path else path
        excluded_files[base_path] = item
        excluded_paths.add(base_path)
    
    # Process excluded files from reverse comparison
    for item in reverse_result.get("excluded_files", []):
        path = item["path"]
        base_path = path.split(" -> ")[0] if " -> " in path else path
        excluded_files[base_path] = item
        excluded_paths.add(base_path)
    
    # Start with a fresh result dictionary
    merged_result = {
        "only_in_dir1": [],
        "only_in_dir2": [],
        "diff_files": [],
        "diff_attrs": [],
        "excluded_files": list(excluded_files.values()),
        "summary": {
            "only_in_dir1_count": 0,
            "only_in_dir2_count": 0,
            "diff_files_count": 0,
            "diff_attrs_count": 0,
            "excluded_files_count": len(excluded_files)
        }
    }
    
    # Helper to normalize paths for lookups
    def get_base_path(path):
        return path.split(" -> ")[0] if " -> " in path else path
    
    # Create sets for file tracking
    paths_in_dir1 = set()
    paths_in_dir2 = set()
    paths_with_content_diff = set()
    paths_with_attr_diff = set()
    
    # First pass: Identify all files that have content differences
    # by checking both forward and reverse results
    content_diff_paths = set()
    
    for item in forward_result["diff_files"]:
        base_path = get_base_path(item["path"])
        if base_path not in excluded_paths:
            content_diff_paths.add(base_path)
    
    for item in reverse_result["diff_files"]:
        base_path = get_base_path(item["path"])
        if base_path not in excluded_paths:
            content_diff_paths.add(base_path)
    
    # Second pass: Process forward result
    for item in forward_result["only_in_dir1"]:
        base_path = get_base_path(item["path"])
        
        # Skip excluded files
        if base_path in excluded_paths:
            continue
        
        # If this file has content differences, don't add it to only_in_dir1
        if base_path in content_diff_paths:
            continue
            
        # Check if this file exists in dir2 (from reverse comparison)
        exists_in_dir2 = False
        for rev_item in reverse_result["only_in_dir2"]:
            if get_base_path(rev_item["path"]) == base_path:
                exists_in_dir2 = True
                break
                
        if exists_in_dir2:
            # This file exists in both dirs but with content differences
            merged_result["diff_files"].append({
                "path": base_path,
                "differences": {
                    "content": True,
                    "size": True,
                    "time": False,
                    "permissions": False,
                    "owner": False,
                    "group": False
                }
            })
            merged_result["summary"]["diff_files_count"] += 1
            paths_with_content_diff.add(base_path)
        else:
            # This file only exists in dir1
            merged_result["only_in_dir1"].append(item)
            merged_result["summary"]["only_in_dir1_count"] += 1
            paths_in_dir1.add(base_path)
    
    # Process forward result - only_in_dir2
    for item in forward_result["only_in_dir2"]:
        base_path = get_base_path(item["path"])
        
        # Skip excluded files
        if base_path in excluded_paths:
            continue
            
        # Skip files already accounted for
        if base_path in paths_in_dir1 or base_path in paths_with_content_diff or base_path in paths_with_attr_diff:
            continue
            
        merged_result["only_in_dir2"].append(item)
        merged_result["summary"]["only_in_dir2_count"] += 1
        paths_in_dir2.add(base_path)
    
    # Process forward result - diff_files (content differences)
    for item in forward_result["diff_files"]:
        base_path = get_base_path(item["path"])
        
        # Skip excluded files
        if base_path in excluded_paths:
            continue
            
        # Skip files already accounted for
        if base_path in paths_with_content_diff:
            continue
            
        merged_result["diff_files"].append(item)
        merged_result["summary"]["diff_files_count"] += 1
        paths_with_content_diff.add(base_path)
    
    # Process forward result - diff_attrs (attribute differences)
    for item in forward_result["diff_attrs"]:
        base_path = get_base_path(item["path"])
        
        # Skip excluded files
        if base_path in excluded_paths:
            continue
            
        # Skip files already accounted for
        if base_path in paths_with_attr_diff or base_path in paths_with_content_diff:
            continue
            
        merged_result["diff_attrs"].append(item)
        merged_result["summary"]["diff_attrs_count"] += 1
        paths_with_attr_diff.add(base_path)
    
    # Process reverse result - only_in_dir2 (these are files only in dir1)
    for item in reverse_result["only_in_dir2"]:
        base_path = get_base_path(item["path"])
        
        # Skip excluded files
        if base_path in excluded_paths:
            continue
            
        # Skip files already accounted for
        if base_path in paths_in_dir1 or base_path in paths_with_content_diff or base_path in paths_with_attr_diff:
            continue
            
        # This file only exists in dir1
        merged_result["only_in_dir1"].append({
            "path": base_path,
            "type": item["type"]
        })
        merged_result["summary"]["only_in_dir1_count"] += 1
        paths_in_dir1.add(base_path)
    
    # Process reverse result - only_in_dir1 (these are files only in dir2)
    for item in reverse_result["only_in_dir1"]:
        base_path = get_base_path(item["path"])
        
        # Skip excluded files
        if base_path in excluded_paths:
            continue
            
        # Skip files already accounted for
        if base_path in paths_in_dir2 or base_path in paths_with_content_diff or base_path in paths_with_attr_diff:
            continue
            
        # This file only exists in dir2
        merged_result["only_in_dir2"].append({
            "path": base_path,
            "type": item["type"]
        })
        merged_result["summary"]["only_in_dir2_count"] += 1
        paths_in_dir2.add(base_path)
    
    # Process reverse result - diff_files (content differences)
    for item in reverse_result["diff_files"]:
        base_path = get_base_path(item["path"])
        
        # Skip excluded files
        if base_path in excluded_paths:
            continue
            
        # Skip files already accounted for
        if base_path in paths_with_content_diff:
            continue
            
        # Use normalized path for consistency
        new_item = item.copy()
        new_item["path"] = base_path
        
        merged_result["diff_files"].append(new_item)
        merged_result["summary"]["diff_files_count"] += 1
        paths_with_content_diff.add(base_path)
    
    # Process reverse result - diff_attrs (attribute differences)
    for item in reverse_result["diff_attrs"]:
        base_path = get_base_path(item["path"])
        
        # Skip excluded files
        if base_path in excluded_paths:
            continue
            
        # Skip files already accounted for
        if base_path in paths_with_attr_diff or base_path in paths_with_content_diff:
            continue
            
        # Use normalized path for consistency
        new_item = item.copy()
        new_item["path"] = base_path
        
        merged_result["diff_attrs"].append(new_item)
        merged_result["summary"]["diff_attrs_count"] += 1
        paths_with_attr_diff.add(base_path)
    
    # Look for files that appear in both only_in_dir1 and only_in_dir2
    # This can happen with symlinks or special handling - we should exclude these
    duplicates = paths_in_dir1.intersection(paths_in_dir2)
    if duplicates:
        # Move these to diff_files
        merged_result["only_in_dir1"] = [item for item in merged_result["only_in_dir1"] 
                                         if get_base_path(item["path"]) not in duplicates]
        merged_result["only_in_dir2"] = [item for item in merged_result["only_in_dir2"] 
                                         if get_base_path(item["path"]) not in duplicates]
        
        # Update counts
        merged_result["summary"]["only_in_dir1_count"] = len(merged_result["only_in_dir1"])
        merged_result["summary"]["only_in_dir2_count"] = len(merged_result["only_in_dir2"])
        
        # Add to diff_files if not already there
        for path in duplicates:
            if path not in paths_with_content_diff and path not in paths_with_attr_diff:
                merged_result["diff_files"].append({
                    "path": path,
                    "differences": {
                        "content": True,
                        "size": True,
                        "time": False,
                        "permissions": False,
                        "owner": False,
                        "group": False
                    }
                })
                merged_result["summary"]["diff_files_count"] += 1
    
    # Copy the total file counts if available
    if "dir1_total_files" in forward_result["summary"] and "dir2_total_files" in forward_result["summary"]:
        merged_result["summary"]["dir1_total_files"] = forward_result["summary"]["dir1_total_files"]
        merged_result["summary"]["dir2_total_files"] = forward_result["summary"]["dir2_total_files"]
    
    return merged_result

def print_comparison_report(result, max_items=10):
    """
    Print a formatted comparison report

    Args:
        result: The comparison result from compare_dirs
        max_items: Maximum number of items to show in each category
    """
    print("\n=== Directory Comparison Report ===\n")

    # Files only in dir1
    print(f"Files only in first directory: {result['summary']['only_in_dir1_count']}")
    for i, item in enumerate(result["only_in_dir1"]):
        if i >= max_items:
            print(f"  ... and {len(result['only_in_dir1']) - max_items} more")
            break
        print(f"  {item['path']}")

    # Files only in dir2
    print(f"\nFiles only in second directory: {result['summary']['only_in_dir2_count']}")
    for i, item in enumerate(result["only_in_dir2"]):
        if i >= max_items:
            print(f"  ... and {len(result['only_in_dir2']) - max_items} more")
            break
        print(f"  {item['path']}")

    # Files with content differences
    print(f"\nFiles with content differences: {result['summary']['diff_files_count']}")
    for i, item in enumerate(result["diff_files"]):
        if i >= max_items:
            print(f"  ... and {len(result['diff_files']) - max_items} more")
            break
        diff_details = []
        for attr, is_different in item["differences"].items():
            if is_different and attr != "content":
                diff_details.append(attr)
        print(f"  {item['path']} (Differences: {', '.join(diff_details)})")

    # Files with attribute differences only
    print(f"\nFiles with attribute differences only: {result['summary']['diff_attrs_count']}")
    for i, item in enumerate(result["diff_attrs"]):
        if i >= max_items:
            print(f"  ... and {len(result['diff_attrs']) - max_items} more")
            break
        diff_details = []
        for attr, is_different in item["differences"].items():
            if is_different:
                diff_details.append(attr)
        print(f"  {item['path']} (Differences: {', '.join(diff_details)})")
        
    # Excluded files
    if "excluded_files" in result and result["excluded_files"]:
        print(f"\nExcluded files: {result['summary'].get('excluded_files_count', 0)}")
        for i, item in enumerate(result["excluded_files"]):
            if i >= max_items:
                print(f"  ... and {len(result['excluded_files']) - max_items} more")
                break
            print(f"  {item['path']} (Reason: {item['reason']})")

    # Summary
    print("\n=== Summary ===")
    total_differences = (
        result["summary"]["only_in_dir1_count"] +
        result["summary"]["only_in_dir2_count"] +
        result["summary"]["diff_files_count"] +
        result["summary"]["diff_attrs_count"]
    )

    if "dir1_total_files" in result["summary"] and "dir2_total_files" in result["summary"]:
        print(f"Total files in first directory: {result['summary']['dir1_total_files']}")
        print(f"Total files in second directory: {result['summary']['dir2_total_files']}")

    print(f"Total differences: {total_differences}")
    
    if "excluded_files_count" in result["summary"] and result["summary"]["excluded_files_count"] > 0:
        print(f"Total excluded files: {result['summary']['excluded_files_count']}")
        print("Note: Symlinks and files with special characters (@#$%) are excluded from comparison.")


# Example usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare two directories using rsync")
    parser.add_argument("dir1", help="First directory")
    parser.add_argument("dir2", help="Second directory")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--no-permissions", action="store_true", help="Ignore permission differences")
    parser.add_argument("--max-items", type=int, default=10, help="Maximum items to show per category")
    parser.add_argument("--one-way", action="store_true", help="Only compare in one direction (faster but may miss some differences)")
    parser.add_argument("--swap", action="store_true", help="Swap dir1 and dir2 (only relevant with --one-way)")

    args = parser.parse_args()

    # Handle directory swapping
    if args.swap:
        args.dir1, args.dir2 = args.dir2, args.dir1

    # Perform the comparison
    result = compare_dirs(args.dir1, args.dir2, not args.no_permissions, not args.one_way)

    # Output the results
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_comparison_report(result, args.max_items)
