# Coding Personas

This module provides 4 distinct coding personas using AmpCLI with specialized system prompts. Each persona has a unique approach to software development challenges.

## Available Personas

### 🏃 Fast Coder (`CodingPersonas.fast_coder()`)

**Philosophy**: Get it working quickly, iterate and improve

**Characteristics**:
- Prioritizes rapid progress and immediate results
- Focuses on implementation over extensive planning
- Writes tests after functionality is working
- Values working software and real-time feedback
- Avoids overthinking - starts coding immediately

**Best Used For**:
- Prototyping and proof-of-concepts
- MVP development
- Quick feature implementations
- Exploring new ideas rapidly

**Example Response Style**:
> "Start with a basic HTML form right now. Get username/password fields working, then add validation later."

---

### 🧪 Test-Focused Coder (`CodingPersonas.test_focused_coder()`)

**Philosophy**: Tests first, comprehensive coverage, dependency injection

**Characteristics**:
- Always writes tests before implementation (TDD)
- Heavy focus on unit tests
- Refactors code specifically for testability
- Uses dependency injection consistently
- Creates mock objects for internal classes (no mocking frameworks)
- Implements full testing pyramid: unit → integration → e2e

**Best Used For**:
- Critical business logic
- Complex algorithms
- Refactoring legacy code
- Building robust, maintainable systems

**Example Response Style**:
> "Write failing tests first! Create a `UserAuthenticator` interface, implement test doubles using inheritance, then build the real implementation."

---

### 👨‍💼 Senior Engineer (`CodingPersonas.senior_engineer()`)

**Philosophy**: Simple, expressive, maintainable code

**Characteristics**:
- Emphasizes clear, intention-revealing naming
- Focuses on code readability and maintainability
- Designs for future refactoring without over-engineering
- Prefers composition over inheritance
- Single responsibility principle
- Clean abstractions and interfaces

**Best Used For**:
- Code reviews
- Refactoring for maintainability
- Establishing coding standards
- Long-term project planning

**Example Response Style**:
> "Use intention-revealing names like `authenticateUser()`. Keep classes focused on single responsibilities. Design clean interfaces that express business logic clearly."

---

### 🏗️ Architect (`CodingPersonas.architect()`)

**Philosophy**: System integrity, consistent patterns, realistic scalability

**Characteristics**:
- Maintains architectural consistency across the system
- Applies design patterns consistently
- Focuses on real scalability requirements (not hypothetical)
- Considers operational complexity
- Thinks about service boundaries and interfaces
- Emphasizes long-term architectural decisions

**Best Used For**:
- System design decisions
- Technology selection
- Scalability planning
- Cross-team consistency
- Large system refactoring

**Example Response Style**:
> "Implement the Command pattern consistently across user actions. Consider service boundaries for future microservice extraction. Design for actual load requirements, not hypothetical scale."

## Usage Examples

### Basic Usage

```python
from coding_personas import CodingPersonas

# Create different personas
fast_coder = CodingPersonas.fast_coder()
test_focused = CodingPersonas.test_focused_coder()
senior_engineer = CodingPersonas.senior_engineer()
architect = CodingPersonas.architect()

# Ask the same question to different personas
question = "How should I implement user authentication?"

fast_response = fast_coder.ask(question)
test_response = test_focused.ask(question)
senior_response = senior_engineer.ask(question)
architect_response = architect.ask(question)

# Clean up
fast_coder._cleanup()
test_focused._cleanup()
senior_engineer._cleanup()
architect._cleanup()
```

### Parallel Development Workflow

```python
import threading
from coding_personas import CodingPersonas

def parallel_code_review():
    """Use different personas for comprehensive code review."""
    
    code_to_review = """
    def process_payment(amount, card_number, user_id):
        # Implementation here
        pass
    """
    
    personas = [
        ("Security", CodingPersonas.senior_engineer()),
        ("Testing", CodingPersonas.test_focused_coder()),
        ("Architecture", CodingPersonas.architect()),
        ("Performance", CodingPersonas.fast_coder())
    ]
    
    results = {}
    threads = []
    
    def review_code(name, persona):
        results[name] = persona.ask(f"Review this payment function: {code_to_review}")
        persona._cleanup()
    
    for name, persona in personas:
        thread = threading.Thread(target=review_code, args=(name, persona))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    return results
```

### Context Manager Usage

```python
from coding_personas import CodingPersonas

# Clean automatic cleanup
with CodingPersonas.fast_coder() as fast_coder:
    response = fast_coder.ask("Build a REST API quickly")
    print(response)
# Automatically cleaned up
```

## When to Use Each Persona

| Scenario | Recommended Persona | Why |
|----------|-------------------|-----|
| **MVP Development** | Fast Coder | Get working version quickly |
| **Legacy Code Refactoring** | Test-Focused Coder | Ensure no regressions |
| **Code Review** | Senior Engineer | Focus on maintainability |
| **System Design** | Architect | Consider long-term implications |
| **Prototyping** | Fast Coder | Rapid iteration |
| **Critical Business Logic** | Test-Focused Coder | Comprehensive testing |
| **Team Onboarding** | Senior Engineer | Establish good practices |
| **Technology Decisions** | Architect | System-wide consistency |

## Testing the Personas

Run the demo scripts to see the personas in action:

```bash
# Quick demo
python test_personas_demo.py

# Comprehensive demonstration
python coding_personas.py
```

## Advanced Usage

### Custom Workflow Combinations

```python
def complete_feature_workflow(feature_description):
    """Use all personas in sequence for complete feature development."""
    
    # 1. Architecture planning
    architect = CodingPersonas.architect()
    architecture = architect.ask(f"Design architecture for: {feature_description}")
    architect._cleanup()
    
    # 2. Test planning
    tester = CodingPersonas.test_focused_coder()
    test_plan = tester.ask(f"Create test plan for: {feature_description}\nArchitecture: {architecture}")
    tester._cleanup()
    
    # 3. Implementation
    fast_coder = CodingPersonas.fast_coder()
    implementation = fast_coder.ask(f"Implement: {feature_description}\nTests: {test_plan}")
    fast_coder._cleanup()
    
    # 4. Code review
    senior = CodingPersonas.senior_engineer()
    review = senior.ask(f"Review implementation: {implementation}")
    senior._cleanup()
    
    return {
        'architecture': architecture,
        'test_plan': test_plan,
        'implementation': implementation,
        'review': review
    }
```

This provides a comprehensive coding assistance system where each persona contributes their specialized expertise to different aspects of software development.
