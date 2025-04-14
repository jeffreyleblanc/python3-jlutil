#!/usr/bin/env python3

import os
import shutil
import tempfile
import subprocess
import json
import time
import stat
import sys
import importlib.util
from pathlib import Path

# Function to find and load the comparison script
def find_and_load_comparison_module():
    """Try to find and load the directory comparison module from various possible filenames"""
    possible_filenames = [
        "directory-compare-simplified.py",
        "simplified_directory_comparison_tool.py",
        "directory_compare_simplified.py"
    ]
    
    for filename in possible_filenames:
        if os.path.exists(filename):
            module_name = os.path.splitext(filename)[0].replace("-", "_")
            spec = importlib.util.spec_from_file_location(module_name, filename)
            if spec:
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                    if hasattr(module, "compare_dirs"):
                        print(f"Found and loaded comparison module from {filename}")
                        return module.compare_dirs, filename
                except Exception as e:
                    print(f"Error loading module from {filename}: {e}")
    
    return None, None

# Import the directory comparison module
compare_dirs_func, script_path = find_and_load_comparison_module()

if compare_dirs_func:
    # We successfully imported the module
    USE_SUBPROCESS = False
    compare_dirs = compare_dirs_func
else:
    # Fall back to subprocess mode
    print("Could not import compare_dirs function. Falling back to subprocess mode.")
    print("Make sure one of these files exists in the current directory:")
    print("  - directory-compare-simplified.py")
    print("  - simplified_directory_comparison_tool.py")
    print("  - directory_compare_simplified.py")
    
    # Try to find the script file again to determine path for subprocess
    if os.path.exists("./directory-compare-simplified.py"):
        SCRIPT_PATH = "./directory-compare-simplified.py"
    elif os.path.exists("./simplified_directory_comparison_tool.py"):
        SCRIPT_PATH = "./simplified_directory_comparison_tool.py"
    elif os.path.exists("./directory_compare_simplified.py"):
        SCRIPT_PATH = "./directory_compare_simplified.py"
    else:
        print("WARNING: Could not find the directory comparison script. Please ensure it exists in the current directory.")
        SCRIPT_PATH = "./directory-compare-simplified.py"  # Default fallback
    
    USE_SUBPROCESS = True

class TestCase:
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.dir1 = None
        self.dir2 = None
        self.expected_result = None
        self.actual_result = None
        self.passed = None
        self.one_way_result = None  # For comparison with one-way mode

    def setup(self, dir1, dir2):
        """
        This method should be implemented by subclasses to set up the test case.
        It should prepare the directory structures in dir1 and dir2.
        """
        self.dir1 = dir1
        self.dir2 = dir2

    def expected_differences(self):
        """
        This method should be implemented by subclasses to define the expected differences.
        Returns a dict with the expected differences similar to the compare_dirs output.
        """
        raise NotImplementedError("Subclasses must implement expected_differences()")

    def run(self):
        """Run the comparison and record the result"""
        if USE_SUBPROCESS:
            # Run the script as a subprocess
            cmd = ["python3", SCRIPT_PATH, self.dir1, self.dir2, "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error running comparison for {self.name}: {result.stderr}")
                self.passed = False
                return
            self.actual_result = json.loads(result.stdout)
            
            # Also run in one-way mode for comparison
            cmd = ["python3", SCRIPT_PATH, self.dir1, self.dir2, "--json", "--one-way"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.one_way_result = json.loads(result.stdout)
        else:
            # Use the imported function
            self.actual_result = compare_dirs(self.dir1, self.dir2)
            self.one_way_result = compare_dirs(self.dir1, self.dir2, bidirectional=False)
        
        self.expected_result = self.expected_differences()
        self.passed = self.validate_results()

    def validate_results(self):
        """
        Validate that the actual results match the expected results.
        This is a simplified validation that checks counts and file paths.
        """
        expected = self.expected_result
        actual = self.actual_result
        
        # Check summary counts
        for key in ["only_in_dir1_count", "only_in_dir2_count", "diff_files_count", "diff_attrs_count"]:
            if expected["summary"][key] != actual["summary"][key]:
                print(f"{self.name}: Expected {key} to be {expected['summary'][key]}, but got {actual['summary'][key]}")
                return False
        
        # Check excluded files count if present in both
        if "excluded_files_count" in expected["summary"] and "excluded_files_count" in actual["summary"]:
            if expected["summary"]["excluded_files_count"] != actual["summary"]["excluded_files_count"]:
                print(f"{self.name}: Expected excluded_files_count to be {expected['summary']['excluded_files_count']}, but got {actual['summary']['excluded_files_count']}")
                return False
        
        # Check that all expected files in dir1 are found
        expected_dir1_paths = {item["path"] for item in expected["only_in_dir1"]}
        actual_dir1_paths = {item["path"] for item in actual["only_in_dir1"]}
        if expected_dir1_paths != actual_dir1_paths:
            print(f"{self.name}: Mismatch in files only in dir1")
            print(f"  Expected: {sorted(expected_dir1_paths)}")
            print(f"  Actual: {sorted(actual_dir1_paths)}")
            return False
            
        # Check that all expected files in dir2 are found
        expected_dir2_paths = {item["path"] for item in expected["only_in_dir2"]}
        actual_dir2_paths = {item["path"] for item in actual["only_in_dir2"]}
        if expected_dir2_paths != actual_dir2_paths:
            print(f"{self.name}: Mismatch in files only in dir2")
            print(f"  Expected: {sorted(expected_dir2_paths)}")
            print(f"  Actual: {sorted(actual_dir2_paths)}")
            return False
            
        # Check that all expected diff files are found
        expected_diff_paths = {item["path"] for item in expected["diff_files"]}
        actual_diff_paths = {item["path"] for item in actual["diff_files"]}
        if expected_diff_paths != actual_diff_paths:
            print(f"{self.name}: Mismatch in files with content differences")
            print(f"  Expected: {sorted(expected_diff_paths)}")
            print(f"  Actual: {sorted(actual_diff_paths)}")
            return False
            
        # Check that all expected attr diff files are found
        expected_attr_paths = {item["path"] for item in expected["diff_attrs"]}
        actual_attr_paths = {item["path"] for item in actual["diff_attrs"]}
        if expected_attr_paths != actual_attr_paths:
            print(f"{self.name}: Mismatch in files with attribute differences")
            print(f"  Expected: {sorted(expected_attr_paths)}")
            print(f"  Actual: {sorted(actual_attr_paths)}")
            return False
        
        # Check excluded files if present in both
        if "excluded_files" in expected and "excluded_files" in actual:
            expected_excluded_paths = {item["path"] for item in expected["excluded_files"]}
            actual_excluded_paths = {item["path"] for item in actual["excluded_files"]}
            if expected_excluded_paths != actual_excluded_paths:
                print(f"{self.name}: Mismatch in excluded files")
                print(f"  Expected: {sorted(expected_excluded_paths)}")
                print(f"  Actual: {sorted(actual_excluded_paths)}")
                return False
        
        return True

    def print_results(self, show_oneway_comparison=True):
        """Print the test results"""
        status = "PASSED" if self.passed else "FAILED"
        print(f"\n=== Test Case: {self.name} - {status} ===")
        print(f"Description: {self.description}")
        
        if not self.passed:
            print("\nExpected Result:")
            print(json.dumps(self.expected_result, indent=2))
            print("\nActual Result:")
            print(json.dumps(self.actual_result, indent=2))
        
        if show_oneway_comparison and self.one_way_result:
            # Compare with one-way result to see if bidirectional found anything different
            one_way_matches = True
            for key in ["only_in_dir1_count", "only_in_dir2_count", "diff_files_count", "diff_attrs_count"]:
                if self.actual_result["summary"][key] != self.one_way_result["summary"][key]:
                    one_way_matches = False
                    break
            
            if not one_way_matches:
                print("\nOne-way vs Bidirectional Comparison Differences:")
                print("The bidirectional comparison found different results than one-way comparison")
                print("Bidirectional summary:", self.actual_result["summary"])
                print("One-way summary:", self.one_way_result["summary"])
                
                # Show specific differences
                bidir_only_in_dir1 = {item["path"] for item in self.actual_result["only_in_dir1"]}
                oneway_only_in_dir1 = {item["path"] for item in self.one_way_result["only_in_dir1"]}
                if bidir_only_in_dir1 != oneway_only_in_dir1:
                    print("\nFiles only in dir1 - Differences:")
                    print("  Only in bidirectional:", sorted(bidir_only_in_dir1 - oneway_only_in_dir1))
                    print("  Only in one-way:", sorted(oneway_only_in_dir1 - bidir_only_in_dir1))
                
                bidir_only_in_dir2 = {item["path"] for item in self.actual_result["only_in_dir2"]}
                oneway_only_in_dir2 = {item["path"] for item in self.one_way_result["only_in_dir2"]}
                if bidir_only_in_dir2 != oneway_only_in_dir2:
                    print("\nFiles only in dir2 - Differences:")
                    print("  Only in bidirectional:", sorted(bidir_only_in_dir2 - oneway_only_in_dir2))
                    print("  Only in one-way:", sorted(oneway_only_in_dir2 - bidir_only_in_dir2))
                
                bidir_diff_files = {item["path"] for item in self.actual_result["diff_files"]}
                oneway_diff_files = {item["path"] for item in self.one_way_result["diff_files"]}
                if bidir_diff_files != oneway_diff_files:
                    print("\nFiles with content differences - Differences:")
                    print("  Only in bidirectional:", sorted(bidir_diff_files - oneway_diff_files))
                    print("  Only in one-way:", sorted(oneway_diff_files - bidir_diff_files))


# Test Case Implementations
class BasicTest(TestCase):
    def __init__(self):
        super().__init__("Basic Test", "Simple test with files unique to each directory and some shared files")
    
    def setup(self, dir1, dir2):
        # Store the directories
        self.dir1 = dir1
        self.dir2 = dir2
        
        # Files only in dir1
        Path(os.path.join(dir1, "file1.txt")).write_text("This is file 1")
        Path(os.path.join(dir1, "file2.txt")).write_text("This is file 2")
        
        # Files only in dir2
        Path(os.path.join(dir2, "file3.txt")).write_text("This is file 3")
        Path(os.path.join(dir2, "file4.txt")).write_text("This is file 4")
        
        # Shared files with same content
        Path(os.path.join(dir1, "shared1.txt")).write_text("Shared content 1")
        Path(os.path.join(dir2, "shared1.txt")).write_text("Shared content 1")
        
        # Shared files with different content
        Path(os.path.join(dir1, "shared2.txt")).write_text("Shared content 2 - version 1")
        Path(os.path.join(dir2, "shared2.txt")).write_text("Shared content 2 - version 2")
    
    def expected_differences(self):
        return {
            "only_in_dir1": [
                {"path": "file1.txt", "type": "file"},
                {"path": "file2.txt", "type": "file"}
            ],
            "only_in_dir2": [
                {"path": "file3.txt", "type": "file"},
                {"path": "file4.txt", "type": "file"}
            ],
            "diff_files": [
                {
                    "path": "shared2.txt",
                    "differences": {
                        "content": True,
                        "size": True,
                        "time": False,
                        "permissions": False,
                        "owner": False,
                        "group": False
                    }
                }
            ],
            "diff_attrs": [],
            "excluded_files": [],
            "summary": {
                "only_in_dir1_count": 2,
                "only_in_dir2_count": 2,
                "diff_files_count": 1,
                "diff_attrs_count": 0,
                "excluded_files_count": 0
            }
        }


class PermissionTest(TestCase):
    def __init__(self):
        super().__init__("Permission Test", "Test with files having different permissions")
    
    def setup(self, dir1, dir2):
        # Store the directories
        self.dir1 = dir1
        self.dir2 = dir2
        
        # Shared files with same content but different permissions
        Path(os.path.join(dir1, "exec.sh")).write_text("#!/bin/bash\necho 'Hello'")
        Path(os.path.join(dir2, "exec.sh")).write_text("#!/bin/bash\necho 'Hello'")
        
        # Make one executable
        os.chmod(os.path.join(dir1, "exec.sh"), stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        os.chmod(os.path.join(dir2, "exec.sh"), stat.S_IRUSR | stat.S_IWUSR)
    
    def expected_differences(self):
        return {
            "only_in_dir1": [],
            "only_in_dir2": [],
            "diff_files": [],
            "diff_attrs": [
                {
                    "path": "exec.sh",
                    "differences": {
                        "content": False,
                        "time": False,
                        "permissions": True,
                        "owner": False,
                        "group": False
                    }
                }
            ],
            "excluded_files": [],
            "summary": {
                "only_in_dir1_count": 0,
                "only_in_dir2_count": 0,
                "diff_files_count": 0,
                "diff_attrs_count": 1,
                "excluded_files_count": 0
            }
        }


class NestedDirTest(TestCase):
    def __init__(self):
        super().__init__("Nested Directory Test", "Test with nested directory structures")
    
    def setup(self, dir1, dir2):
        # Store the directories
        self.dir1 = dir1
        self.dir2 = dir2
        
        # Create nested dirs in dir1
        os.makedirs(os.path.join(dir1, "subdir/deepdir"), exist_ok=True)
        Path(os.path.join(dir1, "subdir/file1.txt")).write_text("Nested file 1")
        Path(os.path.join(dir1, "subdir/deepdir/file2.txt")).write_text("Deep nested file 2")
        
        # Create similar but not identical nested structure in dir2
        os.makedirs(os.path.join(dir2, "subdir/deepdir"), exist_ok=True)
        os.makedirs(os.path.join(dir2, "subdir/otherdir"), exist_ok=True)
        Path(os.path.join(dir2, "subdir/file1.txt")).write_text("Nested file 1 - modified")
        Path(os.path.join(dir2, "subdir/otherdir/file3.txt")).write_text("Other nested file 3")
    
    def expected_differences(self):
        return {
            "only_in_dir1": [
                {"path": "subdir/deepdir/file2.txt", "type": "file"}
            ],
            "only_in_dir2": [
                {"path": "subdir/otherdir/file3.txt", "type": "file"}
            ],
            "diff_files": [
                {
                    "path": "subdir/file1.txt",
                    "differences": {
                        "content": True,
                        "size": True,
                        "time": False,
                        "permissions": False,
                        "owner": False,
                        "group": False
                    }
                }
            ],
            "diff_attrs": [],
            "excluded_files": [],
            "summary": {
                "only_in_dir1_count": 1,
                "only_in_dir2_count": 1,
                "diff_files_count": 1,
                "diff_attrs_count": 0,
                "excluded_files_count": 0
            }
        }


class BidirectionalEdgeTest(TestCase):
    def __init__(self):
        super().__init__("Bidirectional Edge Case", "Test case with symlinks and special characters that should be excluded")
    
    def setup(self, dir1, dir2):
        # Store the directories
        self.dir1 = dir1
        self.dir2 = dir2
        
        # Create a symlink in dir1 pointing to a file 
        Path(os.path.join(dir1, "real_file.txt")).write_text("This is the real file")
        
        # Try to create a symlink - but if it fails (e.g., on Windows), we'll just create a regular file
        try:
            os.symlink(os.path.join(dir1, "real_file.txt"), os.path.join(dir1, "link_to_file.txt"))
        except (OSError, AttributeError):
            # On systems that don't support symlinks, just create a regular file
            Path(os.path.join(dir1, "link_to_file.txt")).write_text("This is a regular file instead of a symlink")
        
        # Create the same files in dir2 but don't use a symlink
        Path(os.path.join(dir2, "real_file.txt")).write_text("This is the real file")
        Path(os.path.join(dir2, "link_to_file.txt")).write_text("This is the real file")
        
        # Create a file with special characters that might trip up rsync
        Path(os.path.join(dir1, "special@#$%.txt")).write_text("Special chars")
        Path(os.path.join(dir2, "special@#$%.txt")).write_text("Different content")
    
    def expected_differences(self):
        # Now we expect symlinks and files with special characters to be excluded
        return {
            "only_in_dir1": [],
            "only_in_dir2": [],
            "diff_files": [],
            "diff_attrs": [],
            "excluded_files": [
                # Expected excluded files - actual details might vary depending on implementation
                {"path": "link_to_file.txt", "reason": "symlink"},
                {"path": "special@#$%.txt", "reason": "special characters"}
            ],
            "summary": {
                "only_in_dir1_count": 0,
                "only_in_dir2_count": 0,
                "diff_files_count": 0,
                "diff_attrs_count": 0,
                "excluded_files_count": 2
            }
        }


class EmptyDirTest(TestCase):
    def __init__(self):
        super().__init__("Empty Directory Test", "Test with an empty directory and a non-empty directory")
    
    def setup(self, dir1, dir2):
        # Store the directories
        self.dir1 = dir1
        self.dir2 = dir2
        
        # dir1 is empty
        # dir2 has some files
        Path(os.path.join(dir2, "file1.txt")).write_text("Content 1")
        Path(os.path.join(dir2, "file2.txt")).write_text("Content 2")
    
    def expected_differences(self):
        return {
            "only_in_dir1": [],
            "only_in_dir2": [
                {"path": "file1.txt", "type": "file"},
                {"path": "file2.txt", "type": "file"}
            ],
            "diff_files": [],
            "diff_attrs": [],
            "excluded_files": [],
            "summary": {
                "only_in_dir1_count": 0,
                "only_in_dir2_count": 2,
                "diff_files_count": 0,
                "diff_attrs_count": 0,
                "excluded_files_count": 0
            }
        }


class HardToReachFileTest(TestCase):
    def __init__(self):
        super().__init__("Hard to Reach File Test", "Test with files that might be harder to compare")
    
    def setup(self, dir1, dir2):
        # Store the directories
        self.dir1 = dir1
        self.dir2 = dir2
        
        # Create a hidden file in dir1
        Path(os.path.join(dir1, ".hidden_file")).write_text("Hidden content")
        
        # Create a hidden directory with a file in dir2
        os.makedirs(os.path.join(dir2, ".hidden_dir"), exist_ok=True)
        Path(os.path.join(dir2, ".hidden_dir/nested_file.txt")).write_text("Nested in hidden dir")
        
        # Create files with dashes but NO special characters
        Path(os.path.join(dir1, "-special-name.txt")).write_text("Special dash file")
        Path(os.path.join(dir2, "-different-name.txt")).write_text("Different dash file")
    
    def expected_differences(self):
        return {
            "only_in_dir1": [
                {"path": ".hidden_file", "type": "file"},
                {"path": "-special-name.txt", "type": "file"}
            ],
            "only_in_dir2": [
                {"path": ".hidden_dir/nested_file.txt", "type": "file"},
                {"path": "-different-name.txt", "type": "file"}
            ],
            "diff_files": [],
            "diff_attrs": [],
            "excluded_files": [],
            "summary": {
                "only_in_dir1_count": 2,
                "only_in_dir2_count": 2,
                "diff_files_count": 0,
                "diff_attrs_count": 0,
                "excluded_files_count": 0
            }
        }


class IdenticalDirsTest(TestCase):
    def __init__(self):
        super().__init__("Identical Directories Test", "Test with two identical directories")
    
    def setup(self, dir1, dir2):
        # Store the directories
        self.dir1 = dir1
        self.dir2 = dir2
        
        # Create identical files in both directories
        for i in range(1, 6):
            Path(os.path.join(dir1, f"file{i}.txt")).write_text(f"Content {i}")
            Path(os.path.join(dir2, f"file{i}.txt")).write_text(f"Content {i}")
        
        # Create an identical subdirectory structure
        os.makedirs(os.path.join(dir1, "subdir"), exist_ok=True)
        os.makedirs(os.path.join(dir2, "subdir"), exist_ok=True)
        Path(os.path.join(dir1, "subdir/nested.txt")).write_text("Nested content")
        Path(os.path.join(dir2, "subdir/nested.txt")).write_text("Nested content")
    
    def expected_differences(self):
        return {
            "only_in_dir1": [],
            "only_in_dir2": [],
            "diff_files": [],
            "diff_attrs": [],
            "excluded_files": [],
            "summary": {
                "only_in_dir1_count": 0,
                "only_in_dir2_count": 0,
                "diff_files_count": 0,
                "diff_attrs_count": 0,
                "excluded_files_count": 0
            }
        }


class ExclusionTest(TestCase):
    def __init__(self):
        super().__init__("Exclusion Test", "Explicitly test exclusion of symlinks and special characters")
    
    def setup(self, dir1, dir2):
        # Store the directories
        self.dir1 = dir1
        self.dir2 = dir2
        
        # Normal files that should be compared
        Path(os.path.join(dir1, "normal1.txt")).write_text("Normal file 1")
        Path(os.path.join(dir2, "normal2.txt")).write_text("Normal file 2")
        
        # Files with special characters that should be excluded
        Path(os.path.join(dir1, "with@sign.txt")).write_text("File with @")
        Path(os.path.join(dir1, "with#hash.txt")).write_text("File with #")
        Path(os.path.join(dir1, "with$dollar.txt")).write_text("File with $")
        Path(os.path.join(dir1, "with%percent.txt")).write_text("File with %")
        
        # Same files in dir2 with different content to ensure they're excluded, not diffed
        Path(os.path.join(dir2, "with@sign.txt")).write_text("Different content @")
        Path(os.path.join(dir2, "with#hash.txt")).write_text("Different content #")
        Path(os.path.join(dir2, "with$dollar.txt")).write_text("Different content $")
        Path(os.path.join(dir2, "with%percent.txt")).write_text("Different content %")
        
        # Try to create a symlink in dir1
        Path(os.path.join(dir1, "target.txt")).write_text("Target file")
        try:
            os.symlink(os.path.join(dir1, "target.txt"), os.path.join(dir1, "symlink.txt"))
        except (OSError, AttributeError):
            # Fallback for systems that don't support symlinks
            Path(os.path.join(dir1, "symlink.txt")).write_text("Pretend symlink")
            
        # Create a different file with the same name in dir2
        Path(os.path.join(dir2, "symlink.txt")).write_text("Not a symlink")
    
    def expected_differences(self):
        return {
            "only_in_dir1": [
                {"path": "normal1.txt", "type": "file"},
                {"path": "target.txt", "type": "file"}
            ],
            "only_in_dir2": [
                {"path": "normal2.txt", "type": "file"}
            ],
            "diff_files": [],
            "diff_attrs": [],
            "excluded_files": [
                {"path": "with@sign.txt", "reason": "special characters"},
                {"path": "with#hash.txt", "reason": "special characters"},
                {"path": "with$dollar.txt", "reason": "special characters"},
                {"path": "with%percent.txt", "reason": "special characters"},
                {"path": "symlink.txt", "reason": "symlink"}
            ],
            "summary": {
                "only_in_dir1_count": 2,
                "only_in_dir2_count": 1,
                "diff_files_count": 0,
                "diff_attrs_count": 0,
                "excluded_files_count": 5
            }
        }


def run_tests():
    """Run all the tests and report results"""
    test_cases = [
        BasicTest(),
        PermissionTest(),
        NestedDirTest(),
        BidirectionalEdgeTest(),
        EmptyDirTest(),
        HardToReachFileTest(),
        IdenticalDirsTest(),
        ExclusionTest()
    ]
    
    # Create a temporary directory for the tests
    with tempfile.TemporaryDirectory() as tmp_root:
        print(f"=== Running {len(test_cases)} test cases ===")
        
        passed_count = 0
        
        for i, test in enumerate(test_cases):
            print(f"\nRunning test {i+1}/{len(test_cases)}: {test.name}")
            
            # Create temporary directories for this test
            dir1 = os.path.join(tmp_root, f"test{i}_dir1")
            dir2 = os.path.join(tmp_root, f"test{i}_dir2")
            os.makedirs(dir1, exist_ok=True)
            os.makedirs(dir2, exist_ok=True)
            
            # Set up the test case
            test.setup(dir1, dir2)
            
            # Run the test
            test.run()
            test.print_results()
            
            if test.passed:
                passed_count += 1
        
        # Print summary
        print(f"\n=== Test Summary ===")
        print(f"Total tests: {len(test_cases)}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {len(test_cases) - passed_count}")
        
        if passed_count == len(test_cases):
            print("\n🎉 All tests passed! The simplified comparison tool is working correctly.")
        else:
            print("\n❌ Some tests failed. Review the output above for details.")


if __name__ == "__main__":
    run_tests()