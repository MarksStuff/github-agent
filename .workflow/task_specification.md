# Feature: 1. Document Symbol Hierarchy
(Extracted from PRD: lsp-feature-extensions-for-coding-agents.md)

# 1. Document Symbol Hierarchy (`textDocument/documentSymbol`)

## Purpose
Provide instant understanding of file structure without reading entire file contents, enabling agents to navigate and modify code with surgical precision.

## Data Returned
- Hierarchical tree of all symbols in a document
- Each symbol includes: name, kind (class/function/method/property), range (start/end positions), detail string, children symbols
- Preserves nesting relationships (methods inside classes, inner functions, nested classes)

## Agent Usage Patterns

### File Understanding:
- Agent receives task: "Add a new method to UserAuthentication class"
- Instead of reading entire 1000-line file, agent queries document symbols
- Gets back structure showing UserAuthentication class at lines 145-455, with existing methods listed
- Agent knows exactly where to insert new method without grep or full file read

### Impact Analysis:
- Before modifying a class, agent can see all its methods/properties instantly
- Can identify if a method already exists with similar name
- Understands class boundaries for proper indentation and placement

### Navigation Optimization:
- Agent can jump directly to relevant code sections
- Provides "table of contents" for large files
- Enables questions like "What methods does this class have?" without file reading

## Storage Requirements
- Symbols linked to file versions/timestamps
- Hierarchical parent-child relationships preserved
- Range information for precise positioning
- Must invalidate when file changes