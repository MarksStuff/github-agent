# Simple Test Design

## Implementation Task: Create a simple calculator

### Requirements
- Create a basic calculator class
- Support addition, subtraction, multiplication, division
- Include proper error handling

### Files to create
- calculator.py
- test_calculator.py

### Implementation Details
```python
class Calculator:
    def add(self, a: float, b: float) -> float:
        return a + b
    
    def subtract(self, a: float, b: float) -> float:
        return a - b
```