# rsync Itemized Output Taxonomy

When running `rsync` with the `-i` flag (itemized changes), it produces output lines that indicate what would happen to each file. Here's a breakdown of the output patterns our code expects and parses:

## Output Line Format

The general format of each itemized output line is:
```
UPDATETYPE METADATA FILENAME
```

Where:
- `UPDATETYPE` is a single character
- `METADATA` is typically 9 characters providing details
- `FILENAME` is the file path (possibly including symlink target information)

## Update Types (First Character)

The first character of each line indicates the basic operation:

| Character | Meaning | Our Processing |
|-----------|---------|----------------|
| `>` | File would be sent from dir1 to dir2 | Added to "only_in_dir1" list |
| `*` | File would be deleted from dir2 | Added to "only_in_dir2" list |
| `c` | File creation (also treated as deletion in reverse) | Added to "only_in_dir2" list |
| `.` | File exists in both dirs but has differences | Added to "diff_files" or "diff_attrs" based on metadata |

## Metadata Flags (Characters 2-10)

The metadata section contains flags that describe the file or its differences:

| Character | Position | Meaning | Our Processing |
|-----------|----------|---------|----------------|
| `d` | Start of metadata | Directory (not a file) | Skipped entirely |
| `s` | Varies | Size is different | Added to "diff_files" if present |
| `t` | Varies | Timestamp is different | Recorded in "differences" dict |
| `p` | Varies | Permissions are different | Recorded in "differences" dict |
| `o` | Varies | Owner is different | Recorded in "differences" dict |
| `g` | Varies | Group is different | Recorded in "differences" dict |
| `L` | Varies | File is a symlink | Used for symlink detection (excluded) |

## Special File Paths

We handle special path formats:

| Path Pattern | Example | Our Processing |
|--------------|---------|----------------|
| Regular path | `file.txt` | Normal processing |
| Symlink | `link.txt -> /target/path` | Excluded with reason "symlink" |
| Special chars | `file@#$%.txt` | Excluded with reason "special characters" |

## Categories in Our Output

We organize files into these categories:

1. **Files only in dir1** (would be sent to dir2)
   - Update type: `>`
   - Not excluded based on path

2. **Files only in dir2** (would be deleted from dir2)
   - Update type: `*` or `c`
   - Not excluded based on path

3. **Files with content differences**
   - Update type: `.`
   - Metadata contains `s` (size difference)
   - Not excluded based on path

4. **Files with attribute differences only**
   - Update type: `.`
   - Metadata does not contain `s`
   - Not excluded based on path

5. **Excluded files**
   - Any file with path containing " -> " (symlinks)
   - Any file with path containing special characters (@, #, $, %)

This categorization allows us to precisely report differences between directories while avoiding problematic edge cases like symlinks and special characters.