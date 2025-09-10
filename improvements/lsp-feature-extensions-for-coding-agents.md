# LSP Feature Extensions for Coding Agents - Specification

## Executive Summary

This document specifies five critical LSP (Language Server Protocol) feature extensions that would transform coding agents from "grep-and-read" patterns to "query-and-navigate" patterns, dramatically improving performance on large codebases. These features leverage existing LSP capabilities that are currently not implemented in our MCP server.

## Core Design Principles

- **Minimize File Reading**: Agents should understand code structure without reading entire files
- **Fast Updates**: Information must update incrementally as code changes
- **Surgical Precision**: Agents should know exactly where to make changes
- **Scalability**: Solutions must work efficiently on very large codebases

## 1. Document Symbol Hierarchy (`textDocument/documentSymbol`)

### Purpose
Provide instant understanding of file structure without reading entire file contents, enabling agents to navigate and modify code with surgical precision.

### Data Returned
- Hierarchical tree of all symbols in a document
- Each symbol includes: name, kind (class/function/method/property), range (start/end positions), detail string, children symbols
- Preserves nesting relationships (methods inside classes, inner functions, nested classes)

### Agent Usage Patterns

**File Understanding:**
- Agent receives task: "Add a new method to UserAuthentication class"
- Instead of reading entire 1000-line file, agent queries document symbols
- Gets back structure showing UserAuthentication class at lines 145-455, with existing methods listed
- Agent knows exactly where to insert new method without grep or full file read

**Impact Analysis:**
- Before modifying a class, agent can see all its methods/properties instantly
- Can identify if a method already exists with similar name
- Understands class boundaries for proper indentation and placement

**Navigation Optimization:**
- Agent can jump directly to relevant code sections
- Provides "table of contents" for large files
- Enables questions like "What methods does this class have?" without file reading

### Storage Requirements
- Symbols linked to file versions/timestamps
- Hierarchical parent-child relationships preserved
- Range information for precise positioning
- Must invalidate when file changes

## 2. Workspace Symbol Search (`workspace/symbol`)

### Purpose
Enable instant, project-wide symbol discovery without recursive grepping, making agents aware of the entire codebase topology.

### Data Returned
- List of all matching symbols across entire workspace
- Each result includes: symbol name, kind, location (file + position), container name (parent class/module)
- Supports fuzzy/partial matching
- Returns results ranked by relevance

### Agent Usage Patterns

**Discovery Queries:**
- Agent needs: "Find all authentication-related classes"
- Searches: "Auth" → gets AuthManager, UserAuth, AuthToken, etc. across all files
- Immediately knows what exists without scanning thousands of files

**Refactoring Support:**
- Task: "Rename all Payment* classes to Transaction*"
- Agent searches "Payment" → gets comprehensive list
- Knows every file that needs modification upfront

**Dependency Understanding:**
- Before creating new class, agent searches to avoid duplicates
- Can find related functionality: "Show all *Validator classes"
- Understands codebase conventions from naming patterns

**Import Resolution:**
- Task: "Use the existing logger"
- Search: "Logger" → finds src/utils/logger.py:Logger
- Agent knows exact import path without guessing

### Storage Requirements
- Full-text searchable symbol index
- Must support partial/fuzzy matching
- Container relationships (symbol → parent class/module)
- Cross-file symbol mapping
- Incremental index updates on file changes

## 3. Semantic Tokens (`textDocument/semanticTokens`)

### Purpose
Provide deep semantic understanding of code elements beyond syntax, enabling agents to make context-aware modifications.

### Data Returned
- Token stream with semantic classifications
- Each token has: type (parameter vs variable vs property), modifiers (readonly, static, async, deprecated)
- Covers entire document with positional mapping
- Language-specific token types (e.g., decorator, type parameter)

### Agent Usage Patterns

**Smart Variable Handling:**
- Agent can distinguish: function parameter vs local variable vs instance variable vs class variable
- Task: "Make all class constants uppercase"
- Semantic tokens identify which variables are class-level constants
- Agent modifies only the correct variables

**Deprecation Awareness:**
- Tokens marked as 'deprecated' warn agent not to use them
- Agent suggests modern alternatives when refactoring
- Avoids propagating deprecated patterns

**Context-Sensitive Edits:**
- Task: "Add type hints to all function parameters"
- Semantic tokens identify exactly which identifiers are parameters
- Agent doesn't confuse with local variables of same name

**Code Quality Patterns:**
- Identify unused variables (marked with special modifier)
- Find async functions for proper await handling
- Recognize readonly/immutable attributes

### Storage Requirements
- Token type enumeration mapping
- Modifier bitmask for each token
- Position mapping (line/column ranges)
- Version tracking for cache invalidation
- Compact storage for large files (thousands of tokens)

## 4. Implementation Discovery (`textDocument/implementation`)

### Purpose
Map abstract interfaces to concrete implementations, crucial for understanding and extending object-oriented codebases.

### Data Returned
- List of all concrete implementations of an interface/protocol/abstract class
- Each result includes file location and symbol information
- Handles inheritance chains and protocol conformance

### Agent Usage Patterns

**Interface Extension:**
- Task: "Add new method to all Repository implementations"
- Agent finds abstract Repository class
- Queries implementations → gets UserRepository, ProductRepository, OrderRepository
- Knows exactly which classes need the new method

**Polymorphic Understanding:**
- Before modifying interface, agent finds all implementations
- Can assess impact: "This change affects 15 implementing classes"
- Ensures consistency across codebase

**Testing Patterns:**
- Task: "Create tests for all Command implementations"
- Agent discovers all concrete command classes
- Generates appropriate test cases for each

**Dependency Injection:**
- Agent understands which concrete classes can satisfy an interface
- Can suggest appropriate implementations for dependency injection
- Knows viable substitutions for refactoring

### Storage Requirements
- Interface → Implementation mapping tables
- Inheritance hierarchy tracking
- Protocol conformance records
- Multi-level inheritance resolution
- Cross-file relationship index

## 5. Real-Time Diagnostics (`textDocument/publishDiagnostics`)

### Purpose
Provide immediate feedback on code validity as changes are made, preventing agents from accumulating errors during multi-step modifications.

### Data Returned
- List of diagnostics (errors, warnings, hints, info)
- Each diagnostic includes: severity, range, message, source (linter/type-checker), code, related information
- Suggestions for fixes (connected to code actions)

### Agent Usage Patterns

**Progressive Validation:**
- Agent makes change → immediately receives diagnostics
- If error introduced: "undefined variable 'user'" → agent knows to add import
- Prevents cascading errors in multi-file changes

**Type Safety Enforcement:**
- Agent adds new parameter to function
- Diagnostics immediately flag all call sites that need updating
- Agent systematically fixes each flagged location

**Import Management:**
- Diagnostics detect missing imports as code is added
- Agent receives specific module suggestions
- Auto-adds required imports before committing

**Code Quality Gates:**
- Agent won't proceed if critical errors exist
- Can distinguish must-fix errors from warnings
- Ensures each intermediate state is valid

**Refactoring Safety:**
- During large refactoring, agent monitors diagnostic count
- If errors spike, agent can rollback and try different approach
- Provides confidence in transformation correctness

### Storage Requirements
- Diagnostic cache per file/version
- Severity level indexing for quick filtering
- Related diagnostic grouping
- Fix suggestion storage
- Historical diagnostic tracking for patterns
- File → Diagnostics mapping with fast updates

## API Design Implications

These features suggest the need for:

1. **Persistent LSP Sessions** - Not one-shot queries
2. **Incremental Update Protocol** - File change notifications
3. **Hierarchical Data Models** - For symbol parent-child relationships  
4. **Full-Text Search Capabilities** - For workspace symbol queries
5. **Version-Aware Caching** - Invalidate on file modifications
6. **Streaming Response Support** - For large semantic token arrays
7. **Relationship Mapping Tables** - For interface→implementation tracking

## Database Schema Considerations

The schema would need:
- **Graph-like structures** for symbol relationships and inheritance
- **Full-text indices** for symbol search
- **Version tracking** for cache invalidation
- **Hierarchical storage** for nested symbols
- **Efficient range queries** for position-based lookups
- **Batch update capabilities** for incremental changes

## Implementation Priority

### Phase 1: Foundation (Highest Impact)
1. **Workspace Symbol Search** - Eliminates most grep operations
2. **Document Symbols** - Provides file structure understanding

### Phase 2: Intelligence
3. **Semantic Tokens** - Enables context-aware modifications
4. **Implementation Discovery** - Critical for OOP codebases

### Phase 3: Quality
5. **Real-Time Diagnostics** - Prevents error accumulation

## Performance Metrics

Expected improvements with full implementation:
- **90% reduction** in grep operations
- **95% reduction** in full file reads
- **10x faster** symbol discovery
- **Near-instant** navigation to code locations
- **Real-time** error detection

## Backwards Compatibility

All features should be:
- Optional and gracefully degrade if LSP server doesn't support them
- Augment, not replace, existing symbol extraction
- Cache results to avoid repeated queries
- Fall back to current grep-based approach when needed

## Conclusion

These five LSP feature extensions would transform the coding agent from a tool that constantly searches and reads files to one that intelligently queries and navigates code. The investment in implementing these features would pay dividends in:

- Reduced token usage (less file reading)
- Faster response times (cached queries vs grep)
- Higher accuracy (semantic understanding)
- Better scalability (works on massive codebases)
- Improved code quality (real-time validation)

The key insight is that LSP servers already maintain these rich indexes - we just need to expose them to our coding agents through the MCP interface.