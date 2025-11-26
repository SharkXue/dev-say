#!/usr/bin/env python3
"""
Format validation script for dev-say.md

This script validates:
- Table format (3 columns: 术语, 国际音标, 简单描述)
- Term entry completeness (all fields non-empty)
- Alphabetical order within alphabetical groups
- Duplicate term detection

Requirements: 3.5, 8.1, 8.2
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class ValidationError:
    """Represents a validation error."""
    
    def __init__(self, line_num: int, message: str, severity: str = "error"):
        self.line_num = line_num
        self.message = message
        self.severity = severity
    
    def __str__(self):
        return f"Line {self.line_num}: [{self.severity.upper()}] {self.message}"


class TermEntry:
    """Represents a term entry in the document."""
    
    def __init__(self, term: str, ipa: str, description: str, line_num: int):
        self.term = term
        self.ipa = ipa
        self.description = description
        self.line_num = line_num
    
    def __repr__(self):
        return f"TermEntry(term='{self.term}', line={self.line_num})"


class DevSayValidator:
    """Validator for dev-say.md format."""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.content: str = ""
        self.lines: List[str] = []
    
    def load_file(self) -> bool:
        """Load the file content."""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.content = f.read()
                self.lines = self.content.split('\n')
            return True
        except FileNotFoundError:
            print(f"Error: File not found: {self.filepath}")
            return False
        except Exception as e:
            print(f"Error reading file: {e}")
            return False
    
    def validate_all(self) -> bool:
        """Run all validations."""
        if not self.load_file():
            return False
        
        self.validate_table_format()
        self.validate_term_completeness()
        self.validate_alphabetical_order()
        self.validate_duplicate_terms()
        
        return len(self.errors) == 0
    
    def validate_table_format(self):
        """Validate that all tables have 3 columns with correct headers."""
        for i, line in enumerate(self.lines, 1):
            if '|' not in line:
                continue
            
            # Check if this is a table header (followed by separator)
            if i < len(self.lines):
                next_line = self.lines[i]
                if '|' in next_line and re.match(r'^[\s|:-]+$', next_line):
                    # This is a table header
                    columns = self._parse_table_row(line)
                    
                    if len(columns) != 3:
                        self.errors.append(ValidationError(
                            i,
                            f"Table header must have 3 columns, found {len(columns)}: {columns}"
                        ))
                        continue
                    
                    # Validate column names
                    self._validate_column_names(columns, i)
    
    def _parse_table_row(self, line: str) -> List[str]:
        """Parse a table row and return cells."""
        cells = line.split('|')
        # Remove leading/trailing empty cells
        if cells and not cells[0].strip():
            cells = cells[1:]
        if cells and not cells[-1].strip():
            cells = cells[:-1]
        return [cell.strip() for cell in cells]
    
    def _validate_column_names(self, columns: List[str], line_num: int):
        """Validate that column names match expected format."""
        columns_lower = [col.lower() for col in columns]
        
        # First column: 术语 or Term
        if not any(keyword in columns_lower[0] for keyword in ['术语', 'term']):
            self.errors.append(ValidationError(
                line_num,
                f"First column should be '术语' or 'Term', found: '{columns[0]}'"
            ))
        
        # Second column: 国际音标 or IPA
        if not any(keyword in columns_lower[1] for keyword in ['国际音标', 'ipa', '音标']):
            self.errors.append(ValidationError(
                line_num,
                f"Second column should be '国际音标' or 'IPA', found: '{columns[1]}'"
            ))
        
        # Third column: 简单描述 or Description
        if not any(keyword in columns_lower[2] for keyword in ['描述', 'description', '简单描述']):
            self.errors.append(ValidationError(
                line_num,
                f"Third column should be '简单描述' or 'Description', found: '{columns[2]}'"
            ))
    
    def validate_term_completeness(self):
        """Validate that all term entries have complete information."""
        term_entries = self._extract_term_entries()
        
        for entry in term_entries:
            # Check for empty fields
            if not entry.term:
                self.errors.append(ValidationError(
                    entry.line_num,
                    "Term name (术语名称) must not be empty"
                ))
            
            if not entry.ipa:
                self.errors.append(ValidationError(
                    entry.line_num,
                    f"IPA notation (国际音标) must not be empty for term '{entry.term}'"
                ))
            elif '/' not in entry.ipa:
                self.warnings.append(ValidationError(
                    entry.line_num,
                    f"IPA notation should be enclosed in forward slashes for term '{entry.term}', found: {entry.ipa}",
                    "warning"
                ))
            
            if not entry.description:
                self.errors.append(ValidationError(
                    entry.line_num,
                    f"Simple description (简单描述) must not be empty for term '{entry.term}'"
                ))
    
    def _extract_term_entries(self) -> List[TermEntry]:
        """Extract all term entries from the document."""
        entries = []
        in_table = False
        
        for i, line in enumerate(self.lines, 1):
            if '|' not in line:
                if not line.strip():
                    in_table = False
                continue
            
            # Check if this is a separator line
            if re.match(r'^[\s|:-]+$', line):
                in_table = True
                continue
            
            # Check if this is a header line
            if i < len(self.lines) and re.match(r'^[\s|:-]+$', self.lines[i]):
                in_table = False
                continue
            
            # If we're in a table, this is a data row
            if in_table and line.strip():
                cells = self._parse_table_row(line)
                
                if len(cells) == 3:
                    entries.append(TermEntry(
                        term=cells[0],
                        ipa=cells[1],
                        description=cells[2],
                        line_num=i
                    ))
                elif len(cells) > 0:
                    # Row exists but doesn't have 3 columns
                    self.errors.append(ValidationError(
                        i,
                        f"Table row must have 3 columns, found {len(cells)}"
                    ))
        
        return entries
    
    def validate_alphabetical_order(self):
        """Validate that terms within each category are in alphabetical order."""
        categories = self._extract_categories_with_terms()
        
        for category_name, terms in categories.items():
            if len(terms) <= 1:
                continue
            
            # Check alphabetical order (case-insensitive)
            term_names = [t.term for t in terms]
            term_names_lower = [t.lower() for t in term_names]
            sorted_names = sorted(term_names_lower)
            
            if term_names_lower != sorted_names:
                # Find the first out-of-order term
                for i in range(len(term_names_lower)):
                    if term_names_lower[i] != sorted_names[i]:
                        self.errors.append(ValidationError(
                            terms[i].line_num,
                            f"Term '{term_names[i]}' is out of alphabetical order in category '{category_name}'. "
                            f"Expected '{sorted_names[i]}' at this position."
                        ))
                        break
    
    def _extract_categories_with_terms(self) -> Dict[str, List[TermEntry]]:
        """Extract alphabetical groups and their terms."""
        categories = {}
        current_category = None
        in_table = False
        
        for i, line in enumerate(self.lines, 1):
            # Check for category heading (## level)
            if line.startswith('## '):
                current_category = line[3:].strip()
                categories[current_category] = []
                in_table = False
                continue
            
            # Check if we're entering a table
            if '|' in line and re.match(r'^[\s|:-]+$', line):
                in_table = True
                continue
            
            # Check if this is a table header
            if '|' in line and i < len(self.lines) and re.match(r'^[\s|:-]+$', self.lines[i]):
                in_table = False
                continue
            
            # Extract term if we're in a table
            if in_table and current_category and '|' in line and line.strip():
                cells = self._parse_table_row(line)
                if len(cells) >= 1 and cells[0]:
                    categories[current_category].append(TermEntry(
                        term=cells[0],
                        ipa=cells[1] if len(cells) > 1 else "",
                        description=cells[2] if len(cells) > 2 else "",
                        line_num=i
                    ))
            
            # Empty line ends the table
            if not line.strip():
                in_table = False
        
        return categories
    
    def validate_duplicate_terms(self):
        """Detect duplicate terms across all categories."""
        all_terms: Dict[str, List[int]] = {}
        
        term_entries = self._extract_term_entries()
        
        for entry in term_entries:
            term_lower = entry.term.lower()
            if term_lower not in all_terms:
                all_terms[term_lower] = []
            all_terms[term_lower].append(entry.line_num)
        
        # Report duplicates
        for term, line_nums in all_terms.items():
            if len(line_nums) > 1:
                self.errors.append(ValidationError(
                    line_nums[0],
                    f"Duplicate term '{term}' found at lines: {', '.join(map(str, line_nums))}"
                ))
    
    def print_results(self):
        """Print validation results."""
        if self.errors:
            print(f"\n❌ Found {len(self.errors)} error(s):\n")
            for error in self.errors:
                print(f"  {error}")
        
        if self.warnings:
            print(f"\n⚠️  Found {len(self.warnings)} warning(s):\n")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All validations passed!")
        
        return len(self.errors) == 0


def main():
    """Main entry point."""
    # Get project root (script is in scripts/ directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    dev_say_path = project_root / "dev-say.md"
    
    print(f"Validating {dev_say_path}...\n")
    
    validator = DevSayValidator(dev_say_path)
    success = validator.validate_all()
    validator.print_results()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
