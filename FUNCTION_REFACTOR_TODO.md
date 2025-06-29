# Function Complexity Refactoring TODO

## Goal: Ensure all functions are ≤50 lines per function complexity guideline

## Priority 1: Critical Violations (>100 lines)

### 1. `src/deletepy/operations/batch_ops.py` - `_handle_auto_delete_operations()` (~193 lines)
- **Current**: Single massive function handling all auto-delete operations
- **Refactor Plan**:
  - Extract `_handle_user_deletions()` for user deletion logic
  - Extract `_handle_identity_unlinking()` for identity unlinking logic
  - Extract `_handle_orphaned_users()` for orphaned user cleanup
  - Extract `_print_operations_summary()` for final summary
  - Keep main function as orchestrator only

## Priority 2: Major Violations (75-100 lines)

### 2. `src/deletepy/operations/batch_ops.py` - `_categorize_users()` (~95 lines)
- **Current**: Complex user categorization logic with multiple conditions
- **Refactor Plan**:
  - Extract `_determine_user_category()` for single user categorization
  - Extract `_is_main_identity()` helper
  - Extract `_has_auth0_main_identity()` helper
  - Simplify main function to iterate and delegate

### 3. `src/deletepy/operations/batch_ops.py` - `_display_search_results()` (~84 lines)
- **Current**: Large function displaying multiple result categories
- **Refactor Plan**:
  - Extract `_print_search_summary()` for basic stats
  - Extract `_print_category_details()` for category-specific output
  - Extract `_print_not_found_ids()` for missing IDs
  - Keep main function as coordinator

### 4. `src/deletepy/utils/csv_utils.py` - `_process_csv_file()` (~79 lines)
- **Current**: Complex CSV processing with multiple branches
- **Refactor Plan**:
  - Extract `_read_csv_headers()` for header processing
  - Extract `_process_csv_rows()` for row processing logic
  - Extract `_handle_csv_conversion()` for output type handling
  - Simplify main function flow

## Priority 3: Moderate Violations (50-75 lines)

### 5. `src/deletepy/utils/csv_utils.py` - `resolve_encoded_username()` (~64 lines)
- **Current**: Mixed Auth0 API resolution and string fallback
- **Refactor Plan**:
  - Extract `_try_auth0_resolution()` for API-based resolution
  - Extract `_apply_string_fallback()` for string replacement
  - Simplify main function logic

### 6. `src/deletepy/utils/csv_utils.py` - `extract_identifiers_from_csv()` (~63 lines)
- **Current**: File processing with multiple format detection branches
- **Refactor Plan**:
  - Extract `_process_detected_file_type()` 
  - Extract `_handle_post_processing()` for conversion logic
  - Simplify main orchestration

### 7. `src/deletepy/utils/csv_utils.py` - `_convert_single_identifier()` (~63 lines)
- **Current**: Complex identifier conversion with multiple fallback strategies
- **Refactor Plan**:
  - Extract `_determine_search_strategy()` 
  - Extract `_try_fallback_resolution()` 
  - Simplify main conversion logic

### 8. `src/deletepy/operations/batch_ops.py` - `find_users_by_social_media_ids()` (~67 lines)
- **Current**: Main function doing search, categorization, and operations
- **Refactor Plan**:
  - Extract `_search_social_ids()` for search loop
  - Extract `_process_search_results()` for result processing  
  - Keep main function as high-level orchestrator

### 9. `src/deletepy/cli/commands.py` - `_process_users()` (~58 lines)
- **Current**: User processing loop with mixed concerns
- **Refactor Plan**:
  - Extract `_process_single_user()` for individual user handling
  - Extract `_collect_processing_results()` for result aggregation
  - Simplify main processing loop

## Refactoring Principles

1. **Single Responsibility**: Each function should have one clear purpose
2. **Extract Method**: Pull out logical chunks into helper functions
3. **Reduce Nesting**: Flatten conditional structures where possible
4. **Error Handling**: Separate error handling from business logic
5. **Maintain API**: Keep public function signatures unchanged

## Success Criteria

- ✅ All functions ≤50 lines
- ✅ No regression in functionality
- ✅ Tests continue to pass
- ✅ Code remains readable and maintainable 