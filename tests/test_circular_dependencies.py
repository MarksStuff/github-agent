"""Test circular dependency detection in symbol hierarchies."""

import unittest

from errors import HierarchyValidationError


class TestCircularDependencies(unittest.TestCase):
    """Test detection and handling of circular dependencies."""

    def test_simple_circular_reference(self):
        """Test detection of A -> B -> A circular reference."""
        # Create symbols with inheritance cycle: ClassA -> ClassB -> ClassA
        symbols = [
            {
                "name": "ClassA",
                "kind": "class",
                "range": {"start": {"line": 0}, "end": {"line": 5}},
                "inherits": "ClassB",  # ClassA inherits from ClassB
            },
            {
                "name": "ClassB",
                "kind": "class",
                "range": {"start": {"line": 6}, "end": {"line": 10}},
                "inherits": "ClassA",  # ClassB inherits from ClassA (cycle!)
            },
        ]

        validator = HierarchyValidator()
        cycles = validator.detect_cycles(symbols)
        
        # Should detect the circular inheritance
        self.assertEqual(len(cycles), 1)
        self.assertEqual(set(cycles[0]), {"ClassA", "ClassB"})

    def test_deep_circular_chain(self):
        """Test detection of A -> B -> C -> D -> A circular chain."""
        symbols = []
        classes = ["ClassA", "ClassB", "ClassC", "ClassD"]

        for i, class_name in enumerate(classes):
            next_class = classes[(i + 1) % len(classes)]
            symbols.append(
                {
                    "name": class_name,
                    "kind": "class",
                    "range": {"start": {"line": i * 10}, "end": {"line": i * 10 + 5}},
                    "inherits": next_class,  # Creates circular inheritance
                }
            )

        validator = HierarchyValidator()
        cycles = validator.detect_cycles(symbols)

        self.assertEqual(len(cycles), 1)
        self.assertEqual(len(cycles[0]), 4)  # Four classes in cycle

    def test_self_referential_symbol(self):
        """Test detection of symbol referencing itself."""
        symbols = [
            {
                "name": "RecursiveClass",
                "kind": "class",
                "range": {"start": {"line": 0}, "end": {"line": 10}},
                "children": [
                    {
                        "name": "RecursiveClass",  # Same name as parent
                        "kind": "class",
                        "range": {"start": {"line": 2}, "end": {"line": 8}},
                        "parent": "RecursiveClass",
                    }
                ],
            }
        ]

        validator = HierarchyValidator()
        cycles = validator.detect_cycles(symbols)
        
        # Should detect a self-reference cycle
        self.assertGreater(len(cycles), 0)
        # The cycle should contain RecursiveClass
        self.assertTrue(any("RecursiveClass" in cycle for cycle in cycles))

    def test_multiple_circular_paths(self):
        """Test handling of multiple circular dependency paths."""
        # Graph with multiple cycles: A -> B -> C -> A and B -> D -> E -> B
        symbols = {
            "A": {"children": ["B"], "parents": ["C"]},
            "B": {"children": ["C", "D"], "parents": ["A", "E"]},
            "C": {"children": ["A"], "parents": ["B"]},
            "D": {"children": ["E"], "parents": ["B"]},
            "E": {"children": ["B"], "parents": ["D"]},
        }

        graph = DependencyGraph(symbols)
        cycles = graph.find_all_cycles()

        self.assertGreaterEqual(len(cycles), 2)

        # Verify both cycles detected
        cycle_sets = [set(cycle) for cycle in cycles]
        self.assertIn({"A", "B", "C"}, cycle_sets)
        self.assertIn({"B", "D", "E"}, cycle_sets)

    def test_circular_import_detection(self):
        """Test detection of circular imports between modules."""
        modules = {
            "module_a.py": ["from module_b import ClassB"],
            "module_b.py": ["from module_c import ClassC"],
            "module_c.py": ["from module_a import ClassA"],
        }

        import_analyzer = ImportAnalyzer()
        circular_imports = import_analyzer.detect_circular_imports(modules)

        self.assertEqual(len(circular_imports), 1)
        self.assertEqual(
            set(circular_imports[0]), {"module_a.py", "module_b.py", "module_c.py"}
        )

    def test_inheritance_cycle_detection(self):
        """Test detection of circular inheritance chains."""
        class_hierarchy = {
            "BaseClass": None,
            "DerivedA": "DerivedB",  # A inherits from B
            "DerivedB": "DerivedC",  # B inherits from C
            "DerivedC": "DerivedA",  # C inherits from A (cycle!)
            "SafeClass": "BaseClass",
        }

        validator = InheritanceValidator()
        cycles = validator.find_inheritance_cycles(class_hierarchy)

        self.assertEqual(len(cycles), 1)
        self.assertIn("DerivedA", cycles[0])
        self.assertIn("DerivedB", cycles[0])
        self.assertIn("DerivedC", cycles[0])
        self.assertNotIn("BaseClass", cycles[0])
        self.assertNotIn("SafeClass", cycles[0])

    def test_break_circular_dependency(self):
        """Test breaking circular dependencies when detected."""
        symbols_with_cycle = [
            {"name": "A", "depends_on": ["B"]},
            {"name": "B", "depends_on": ["C"]},
            {"name": "C", "depends_on": ["A"]},
        ]

        resolver = CircularDependencyResolver()
        resolved = resolver.break_cycles(symbols_with_cycle)

        # Verify cycle is broken
        validator = HierarchyValidator()
        cycles = validator.detect_cycles(resolved)
        self.assertEqual(len(cycles), 0)

        # Verify minimal changes made
        changes = resolver.get_changes()
        self.assertLessEqual(len(changes), 1)  # Should break only one link

    def test_nested_class_circular_reference(self):
        """Test circular references in nested class hierarchies."""
        nested_structure = {
            "OuterClass": {
                "InnerClassA": {
                    "DeepClass": {
                        "parent": "AnotherDeep"  # References sibling's child
                    }
                },
                "InnerClassB": {
                    "AnotherDeep": {
                        "parent": "DeepClass"  # Creates cycle back
                    }
                },
            }
        }

        with self.assertRaises(HierarchyValidationError) as ctx:
            validate_nested_hierarchy(nested_structure)

        error_msg = str(ctx.exception)
        self.assertIn("circular", error_msg.lower())
        self.assertIn("DeepClass", error_msg)

    def test_method_call_circular_dependency(self):
        """Test circular dependencies in method call chains."""
        call_graph = {
            "method_a": ["method_b", "method_c"],
            "method_b": ["method_d"],
            "method_c": ["method_e"],
            "method_d": ["method_a"],  # Creates cycle
            "method_e": [],
        }

        analyzer = CallGraphAnalyzer()
        cycles = analyzer.find_recursive_calls(call_graph)

        self.assertEqual(len(cycles), 1)
        cycle = cycles[0]
        self.assertIn("method_a", cycle)
        self.assertIn("method_b", cycle)
        self.assertIn("method_d", cycle)
        self.assertNotIn("method_c", cycle)
        self.assertNotIn("method_e", cycle)

    def test_async_circular_dependency_detection(self):
        """Test detection of circular dependencies in async operations."""
        import asyncio

        async def detect_async_cycles():
            tasks = {
                "task_a": ["task_b"],
                "task_b": ["task_c", "task_d"],
                "task_c": ["task_a"],  # Cycle
                "task_d": [],
            }

            detector = AsyncCycleDetector()
            cycles = await detector.detect_cycles_async(tasks)
            return cycles

        cycles = asyncio.run(detect_async_cycles())
        self.assertEqual(len(cycles), 1)
        self.assertEqual(set(cycles[0]), {"task_a", "task_b", "task_c"})


class HierarchyValidator:
    """Validates symbol hierarchies for circular dependencies."""

    def detect_cycles(self, symbols):
        """Detect all cycles in symbol dependency graph."""
        # Build adjacency list from symbols
        graph = {}
        if isinstance(symbols, list):
            for symbol in symbols:
                name = symbol.get("name")
                graph[name] = []
                
                # Add children as dependencies
                for child in symbol.get("children", []):
                    child_name = child.get("name") if isinstance(child, dict) else child
                    if child_name:
                        graph[name].append(child_name)
                
                # Add inheritance as dependency
                if "inherits" in symbol:
                    graph[name].append(symbol["inherits"])
        
        # Use DFS to find cycles
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node, path):
            if node in rec_stack:
                # Found cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                if cycle not in cycles:
                    cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            # Visit neighbors
            for neighbor in graph.get(node, []):
                dfs(neighbor, path[:])

            rec_stack.remove(node)

        # Check all nodes
        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles


class DependencyGraph:
    """Represents dependency relationships between symbols."""

    def __init__(self, symbols):
        self.symbols = symbols

    def find_all_cycles(self):
        """Find all simple cycles in the dependency graph."""
        cycles = []

        for start_node in self.symbols:
            visited = set()
            self._find_cycles_from_node(start_node, [start_node], visited, cycles)

        # Remove duplicate cycles
        unique_cycles = []
        for cycle in cycles:
            cycle_set = set(cycle)
            if not any(cycle_set == set(c) for c in unique_cycles):
                unique_cycles.append(cycle)

        return unique_cycles

    def _find_cycles_from_node(self, node, path, visited, cycles):
        """DFS to find cycles starting from a node."""
        if node in visited and node == path[0] and len(path) > 1:
            cycles.append(path[:])
            return

        if node in visited:
            return

        visited.add(node)

        for child in self.symbols.get(node, {}).get("children", []):
            self._find_cycles_from_node(child, path + [child], visited.copy(), cycles)


class ImportAnalyzer:
    """Analyzes import statements for circular dependencies."""

    def detect_circular_imports(self, modules):
        """Detect circular import chains."""
        import_graph = self._build_import_graph(modules)
        
        # Use Tarjan's algorithm for strongly connected components
        cycles = self._find_strong_components(import_graph)
        
        # Filter to only return actual cycles (components with more than 1 node or self-loops)
        actual_cycles = []
        for cycle in cycles:
            if len(cycle) > 1:
                actual_cycles.append(cycle)
            elif len(cycle) == 1:
                # Check for self-loop
                node = cycle[0]
                if node in import_graph.get(node, []):
                    actual_cycles.append(cycle)
        
        return actual_cycles

    def _build_import_graph(self, modules):
        """Build graph of import dependencies."""
        graph = {}

        for module, imports in modules.items():
            graph[module] = []
            for imp in imports:
                # Parse import statement
                if "from " in imp:
                    parts = imp.split()
                    if len(parts) >= 2:
                        imported_module = parts[1].split(".")[0] + ".py"
                        if imported_module in modules:
                            graph[module].append(imported_module)

        return graph

    def _find_strong_components(self, graph):
        """Find strongly connected components using Tarjan's algorithm."""
        index_counter = [0]
        stack = []
        lowlinks = {}
        index = {}
        on_stack = {}
        sccs = []
        
        def strongconnect(node):
            index[node] = index_counter[0]
            lowlinks[node] = index_counter[0]
            index_counter[0] += 1
            on_stack[node] = True
            stack.append(node)
            
            # Visit successors
            for successor in graph.get(node, []):
                if successor not in index:
                    strongconnect(successor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[successor])
                elif on_stack.get(successor, False):
                    lowlinks[node] = min(lowlinks[node], index[successor])
            
            # If node is a root node, pop the stack and return SCC
            if lowlinks[node] == index[node]:
                component = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    component.append(w)
                    if w == node:
                        break
                sccs.append(component)
        
        for node in graph:
            if node not in index:
                strongconnect(node)
        
        return sccs


class InheritanceValidator:
    """Validates class inheritance hierarchies."""

    def find_inheritance_cycles(self, class_hierarchy):
        """Find cycles in inheritance chain."""
        cycles = []
        processed = set()

        for class_name, parent in class_hierarchy.items():
            if class_name not in processed and parent:
                visited = set()
                if self._has_inheritance_cycle(class_name, class_hierarchy, visited):
                    cycle = self._get_cycle_path(class_name, class_hierarchy)
                    if cycle:
                        # Normalize cycle to start from smallest element
                        min_idx = cycle.index(min(cycle))
                        normalized = cycle[min_idx:] + cycle[:min_idx]
                        
                        # Check if this cycle is already found
                        if not any(set(normalized) == set(c) for c in cycles):
                            cycles.append(normalized)
                            processed.update(normalized)

        return cycles

    def _has_inheritance_cycle(self, class_name, hierarchy, visited):
        """Check if class has circular inheritance."""
        if class_name in visited:
            return True

        visited.add(class_name)
        parent = hierarchy.get(class_name)

        if parent and parent in hierarchy:
            return self._has_inheritance_cycle(parent, hierarchy, visited)

        return False

    def _get_cycle_path(self, start_class, hierarchy):
        """Get the path of the inheritance cycle."""
        path = [start_class]
        current = hierarchy.get(start_class)

        while current and current not in path:
            path.append(current)
            current = hierarchy.get(current)

        if current in path:
            cycle_start = path.index(current)
            return path[cycle_start:]

        return []


class CircularDependencyResolver:
    """Resolves circular dependencies by breaking cycles."""

    def __init__(self):
        self.changes = []

    def break_cycles(self, symbols):
        """Break circular dependencies in symbols."""
        # Deep copy to avoid modifying original
        import copy

        resolved = copy.deepcopy(symbols)

        # Find weakest link in each cycle
        validator = HierarchyValidator()
        cycles = validator.detect_cycles(resolved)

        for cycle in cycles:
            # Break at the weakest point
            weakest_link = self._find_weakest_link(cycle, resolved)
            if weakest_link:
                self._remove_dependency(weakest_link, resolved)
                self.changes.append(weakest_link)

        return resolved

    def _find_weakest_link(self, cycle, symbols):
        """Find the best dependency to remove."""
        # Simple heuristic: remove the last link in the cycle
        if len(cycle) >= 2:
            return (cycle[-1], cycle[0])
        return None

    def _remove_dependency(self, link, symbols):
        """Remove a dependency link."""
        source, target = link
        for symbol in symbols:
            if symbol.get("name") == source:
                if "depends_on" in symbol and target in symbol["depends_on"]:
                    symbol["depends_on"].remove(target)

    def get_changes(self):
        """Get list of changes made."""
        return self.changes


class CallGraphAnalyzer:
    """Analyzes method call graphs for recursion."""

    def find_recursive_calls(self, call_graph):
        """Find recursive call chains."""
        all_cycles = []
        processed = set()

        for method in call_graph:
            if method not in processed:
                visited = set()
                path = []
                cycle = self._find_recursion(method, call_graph, visited, path)
                if cycle:
                    # Normalize cycle to avoid duplicates
                    cycle_set = set(cycle)
                    if not any(cycle_set == set(c) for c in all_cycles):
                        all_cycles.append(cycle)
                        processed.update(cycle)

        return all_cycles

    def _find_recursion(self, method, graph, visited, path):
        """DFS to find recursive calls."""
        if method in path:
            # Found recursion - extract the cycle
            cycle_start = path.index(method)
            return path[cycle_start:]

        if method in visited:
            return None

        visited.add(method)
        path.append(method)

        for called_method in graph.get(method, []):
            cycle = self._find_recursion(called_method, graph, visited.copy(), path[:])
            if cycle:
                return cycle

        return None


class AsyncCycleDetector:
    """Detects cycles in async task dependencies."""

    async def detect_cycles_async(self, tasks):
        """Asynchronously detect dependency cycles."""
        import asyncio

        cycles = []

        async def check_task(task_name, path, visited):
            if task_name in path:
                # Found cycle
                cycle_start = path.index(task_name)
                cycle = path[cycle_start:] + [task_name]
                if set(cycle) not in [set(c) for c in cycles]:
                    cycles.append(cycle)
                return

            if task_name in visited:
                return

            visited = visited.copy()
            visited.add(task_name)
            new_path = path + [task_name]

            # Check dependencies
            deps = tasks.get(task_name, [])
            if deps:
                await asyncio.gather(*[check_task(dep, new_path, visited) for dep in deps])

        # Check all tasks
        await asyncio.gather(*[check_task(task, [], set()) for task in tasks])

        return cycles


def validate_nested_hierarchy(structure):
    """Validate nested class hierarchy for circular references."""
    # Build a map of all class names and dependency graph
    all_classes = set()
    dependencies = {}
    
    def extract_classes(node, current_path=""):
        for key, value in node.items():
            full_name = f"{current_path}.{key}" if current_path else key
            all_classes.add(key)  # Add short name
            all_classes.add(full_name)  # Add full path
            
            if isinstance(value, dict):
                # Check for parent reference
                if "parent" in value:
                    parent_ref = value["parent"]
                    if key not in dependencies:
                        dependencies[key] = []
                    dependencies[key].append(parent_ref)
                
                # Process nested classes
                for nested_key, nested_value in value.items():
                    if nested_key != "parent" and isinstance(nested_value, dict):
                        extract_classes({nested_key: nested_value}, full_name)
    
    extract_classes(structure)
    
    # Check for cycles in the dependency graph
    def has_cycle(node, visited, rec_stack, path):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in dependencies.get(node, []):
            if neighbor in rec_stack:
                # Found a cycle
                cycle_path = path[path.index(neighbor):] + [neighbor]
                raise HierarchyValidationError(
                    f"Circular reference detected: {' -> '.join(cycle_path)} creates cycle"
                )
            elif neighbor not in visited and neighbor in dependencies:
                has_cycle(neighbor, visited, rec_stack, path[:])
        
        rec_stack.remove(node)
        return False
    
    # Check all nodes for cycles
    visited = set()
    for node in dependencies:
        if node not in visited:
            has_cycle(node, visited, set(), [])


if __name__ == "__main__":
    unittest.main()
