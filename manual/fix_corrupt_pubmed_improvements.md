# PubMed Corruption Fix Improvements

## Overview

The `fix_corrupt_pubmed_imports.py` module has been significantly improved to better distinguish between legitimate article updates and data corruption. Previously, the module relied solely on text length comparisons, which could incorrectly flag legitimate article revisions as corruption.

## Key Improvements

### 1. Intelligent Update Detection

The module now uses revision dates from PubMed XML files to determine if changes represent legitimate updates:

- **Date-based Detection**: Compares `date_revised` from XML with the database record's `updated_date`
- **Smart Logic**: If XML revision date is newer than database update date, treats changes as legitimate updates
- **Fallback**: When no clear update indication exists, falls back to length-based corruption detection

### 2. Improved Comparison Logic

The `compare_articles()` method now follows this enhanced logic:

1. **Check for Legitimate Updates**: Use `_is_legitimate_update()` to analyze revision dates
2. **For Legitimate Updates**: Accept XML version regardless of length differences
3. **For Suspected Corruption**: Use length-based detection with user confirmation
4. **Special Cases**: Always keep longer MeSH terms without user confirmation

### 3. Enhanced User Prompts

When user confirmation is needed, the prompts now provide better context:

- **Clear Distinction**: Different messages for legitimate updates vs suspected corruption
- **Contextual Information**: Explains what each scenario means
- **Better Guidance**: Provides appropriate recommendations based on the situation

### 4. Robust Date Parsing

The date comparison logic handles various date formats:

- **XML Dates**: Parses `YYYY-MM-DD` format from PubMed XML
- **Database Dates**: Handles both date and datetime formats
- **Error Handling**: Graceful fallback when date parsing fails

## Technical Details

### Update Detection Method

```python
def _is_legitimate_update(self, new_article: Dict[str, Any], existing_article: Dict[str, Any]) -> bool:
    """
    Determine if the XML article represents a legitimate update vs potential corruption.
    
    Uses revision dates and other metadata to make this determination.
    """
```

**Logic Flow**:
1. Extract `date_revised` from XML article
2. Extract `updated_date` from database record
3. Parse both dates to comparable format
4. Return `True` if XML revision date > database update date

### Enhanced Comparison Logic

**For Legitimate Updates**:
- Accept all XML changes regardless of length
- Log as "updated in legitimate revision"

**For Suspected Corruption**:
- Longer XML version → Accept (likely corruption fix)
- Shorter XML version → Ask user (suspicious)
- Same length, different content → Accept (assume correct)

**Special Handling**:
- MeSH terms: Always keep longer version without asking
- User prompts: Provide context about update vs corruption

## Usage Examples

### Scenario 1: Legitimate Article Update
```
XML: date_revised = "2024-01-15"
DB:  updated_date = "2024-01-10"
Result: Treat as legitimate update, accept XML changes
```

### Scenario 2: Suspected Corruption
```
XML: date_revised = "2024-01-05" (or missing)
DB:  updated_date = "2024-01-10"
Result: Use corruption detection logic
```

### Scenario 3: Length-based Detection
```
XML abstract: 150 characters
DB abstract:  300 characters
No clear update indication
Result: Ask user for confirmation with context
```

## Benefits

1. **Reduced False Positives**: Legitimate article revisions no longer flagged as corruption
2. **Better User Experience**: Clear context when user input is needed
3. **Automated Handling**: Most legitimate updates processed automatically
4. **Robust Logic**: Handles various date formats and edge cases
5. **Preserved Safety**: Still catches and fixes actual corruption

## Migration Notes

- **Backward Compatible**: Existing functionality preserved
- **Enhanced Logic**: Builds on existing length-based detection
- **No Database Changes**: Uses existing `updated_date` field
- **Improved Logging**: Better visibility into decision-making process

## Testing

The improvements have been tested with various scenarios:
- Legitimate updates with newer revision dates
- Suspected corruption with older/missing revision dates
- Edge cases with missing dates or parsing errors
- Different date formats (date vs datetime)

All test cases pass, confirming the logic works as expected.
