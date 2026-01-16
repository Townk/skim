# Implementation Tasks

## 1. Update Keycode Loader

- [x] 1.1 Add `macro_functions` to `merge_mappings` result dictionary
- [x] 1.2 Add `modifier_union` to `merge_mappings` result dictionary
- [x] 1.3 Update loader tests for new mapping sections

## 2. Refactor Keycode Transformer

- [x] 2.1 Update `__init__` to accept `macro_functions` and `modifier_union` parameters
- [x] 2.2 Remove `modifiers` and `layer_symbols` parameters from `__init__`
- [x] 2.3 Implement `_parse_function_arguments` method for argument extraction
- [x] 2.4 Implement `_resolve_layer_argument` method for `#N;` placeholder
- [x] 2.5 Implement `_resolve_keycode_argument` method for `@N;` placeholder
- [x] 2.6 Implement `_resolve_modifier_union` method for `MOD_X|MOD_Y` patterns
- [x] 2.7 Implement `_parse_macro_function` method as unified entry point
- [x] 2.8 Update `transform` method to use new macro function pipeline
- [x] 2.9 Remove `_parse_modifier_function` method
- [x] 2.10 Remove `_parse_layer_function` method
- [x] 2.11 Update `extract_layer_id` to work with new structure

## 3. Update Image Generator

- [x] 3.1 Update `KeycodeTransformer` instantiation to pass new mapping sections
- [x] 3.2 Remove passing of deprecated `modifiers` and `layer_symbols` sections

## 4. Update Tests

- [x] 4.1 Update `KeycodeMappingLoader` unit tests
- [x] 4.2 Rewrite `KeycodeTransformer` unit tests for new interface
- [x] 4.3 Add tests for macro function placeholder resolution
- [x] 4.4 Add tests for modifier union resolution
- [x] 4.5 Add tests for hold-tap keys (LT, MT, *_T functions)
- [x] 4.6 Add tests for nested macro functions
- [x] 4.7 Update integration tests (mock fixtures)

## 5. Documentation

- [x] 5.1 Update docstrings in `keycode_transformer.py`
- [x] 5.2 Update docstrings in `keycode_loader.py`
