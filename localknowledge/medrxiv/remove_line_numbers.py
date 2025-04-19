"""
Remove line numbers from converted PDF markdown

This script provides functions to remove sequential line numbers that appear at the beginning
of lines in markdown text extracted from PDFs using pymupdf4llm.
"""

import re
import os
import sys


def remove_sequential_line_numbers(text):
    """
    Remove sequential line numbers from lines in markdown text.
    Handles various special cases:
    1. Preserves numbered lists (numbers followed by periods)
    2. Handles markdown headings with line numbers (like ## 51 Introduction)
    3. Handles line numbers that may appear after various markdown elements
    4. Handles documents where text appears before line numbers start
    
    Parameters:
    - text: String containing markdown text with line numbers
    
    Returns:
    - Cleaned text with sequential line numbers removed
    """
    # Split the text into lines
    lines = text.split('\n')
    cleaned_lines = []
    
    # Pattern for standard line numbers at the beginning of a line
    line_number_pattern = re.compile(r'^\s*(\d+)\s+(.*)$')
    
    # Pattern for markdown headings with line numbers (e.g., ## 51 Introduction)
    # This handles cases like "# 1 TITLE" or "### 3 SECTION"
    heading_line_number_pattern = re.compile(r'^(\s*#{1,6}\s+)(\d+)(\s+.*)$')
    
    # Pattern for numbered lists - numbers that are followed by a period and space
    # These should be preserved as they're not line numbers
    numbered_list_pattern = re.compile(r'^\s*\d+\.\s+.*$')
    
    # Pattern for line numbers that appear on their own line
    # Example: "2" on a line by itself
    isolated_number_pattern = re.compile(r'^\s*(\d+)\s*$')
    
    # Keep track of the last number seen to ensure we only remove sequential numbers
    # We start with None and will pick up the sequence once we detect it
    last_number = None
    in_sequence = False
    
    for i, line in enumerate(lines):
        # Skip numbered list items (we want to preserve these)
        if numbered_list_pattern.match(line):
            cleaned_lines.append(line)
            continue
        
        # Check for line numbers in markdown headings
        heading_match = heading_line_number_pattern.match(line)
        if heading_match:
            heading_prefix = heading_match.group(1)  # The heading markers (##)
            number = int(heading_match.group(2))     # The line number
            content = heading_match.group(3)         # The rest of the line
            
            # Check if this is likely a line number (sequential) rather than an intended heading number
            if last_number is None or number == last_number + 1:
                # This looks like a line number in a heading, so remove it
                cleaned_lines.append(f"{heading_prefix}{content.lstrip()}")
                last_number = number
                in_sequence = True
            else:
                # This doesn't look like a sequential line number, keep it
                cleaned_lines.append(line)
            continue
        
        # Check for isolated numbers that might be line numbers
        isolated_match = isolated_number_pattern.match(line)
        if isolated_match:
            number = int(isolated_match.group(1))
            if last_number is None or number == last_number + 1:
                # This is likely a lone line number, so remove it completely
                # Don't append anything to cleaned_lines
                last_number = number
                in_sequence = True
                continue
            else:
                # Not in sequence, treat as normal content
                cleaned_lines.append(line)
                continue
        
        # Check for regular line numbers at beginning of lines
        match = line_number_pattern.match(line)
        if match:
            number = int(match.group(1))
            content = match.group(2)
            
            # Check if this number is sequential or the start of a sequence
            if last_number is None or number == last_number + 1:
                # This is a sequential line number, so remove it
                cleaned_lines.append(content)
                last_number = number
                in_sequence = True
            else:
                # This is not a sequential line number, so keep the line as is
                cleaned_lines.append(line)
                # If the number is small (like 1 or 2) and we haven't detected a sequence yet,
                # it could be the start of a new sequence
                if number < 3 and not in_sequence:
                    last_number = number
                    in_sequence = True
                else:
                    last_number = None
                    in_sequence = False
        else:
            # Line doesn't start with a number, keep as is
            cleaned_lines.append(line)
            # Don't reset the sequence detection if we're just encountering non-numbered
            # lines in the middle of a sequence (e.g., blank lines or special sections)
            # Only reset if we see many non-numbered lines in a row
            if in_sequence and i > 0 and i < len(lines) - 1:
                # Check if we've seen too many non-numbered lines to still consider this a sequence
                non_numbered_streak = 1
                for j in range(i+1, min(i+4, len(lines))):
                    if not line_number_pattern.match(lines[j]) and not isolated_number_pattern.match(lines[j]):
                        non_numbered_streak += 1
                
                # If there are 3+ consecutive non-numbered lines, we're probably out of the sequence
                if non_numbered_streak > 2:
                    last_number = None
                    in_sequence = False
    
    # Join the lines back together
    return '\n'.join(cleaned_lines)


def clean_markdown_file(input_path, output_path=None):
    """
    Read a markdown file, remove sequential line numbers, and save to output file.
    If no output path is provided, it will overwrite the input file.
    
    Parameters:
    - input_path: Path to the input markdown file
    - output_path: Path to save the cleaned markdown file (default: overwrite input)
    
    Returns:
    - Path to the output file
    """
    try:
        # Read the input file
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Clean the content
        cleaned_content = remove_sequential_line_numbers(content)
        
        # Determine output path
        if not output_path:
            output_path = input_path
        
        # Write to the output file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        
        return output_path
    
    except Exception as e:
        print(f"Error processing file {input_path}: {str(e)}")
        return None


if __name__ == "__main__":
    # Simple command line interface
    if len(sys.argv) < 2:
        print("Usage: python remove_line_numbers.py input_file [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = clean_markdown_file(input_file, output_file)
    if result:
        print(f"Successfully cleaned and saved to {result}")
