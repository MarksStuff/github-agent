#!/usr/bin/env python3
"""
Demo script showing the 4 coding personas in action.
"""

from coding_personas import CodingPersonas


def quick_persona_test():
    """Quick test showing personality differences."""

    task = "I need to build a simple calculator function that adds two numbers. How should I start?"

    print("TASK:", task)
    print("=" * 80)

    # Test each persona
    personas = [
        ("Fast Coder", CodingPersonas.fast_coder),
        ("Test-Focused Coder", CodingPersonas.test_focused_coder),
        ("Senior Engineer", CodingPersonas.senior_engineer),
        ("Architect", CodingPersonas.architect),
    ]

    for name, factory in personas:
        print(f"\n🚀 {name.upper()}:")
        print("-" * 40)

        try:
            persona = factory()
            response = persona.ask(task)
            # Show first few lines to see the personality
            lines = response.split("\n")[:3]
            for line in lines:
                if line.strip():
                    print(f"  {line}")
            persona._cleanup()

        except Exception as e:
            print(f"  Error: {e}")


def detailed_comparison():
    """Detailed comparison showing how each persona approaches a complex problem."""

    problem = """I have a Python function that's becoming unwieldy:

def handle_user_request(request_data):
    if not request_data:
        return {"error": "No data"}

    user_id = request_data.get("user_id")
    action = request_data.get("action")

    if action == "get_profile":
        # Database call
        db = connect_db()
        user = db.query("SELECT * FROM users WHERE id = ?", user_id)
        return {"profile": user[0] if user else None}

    elif action == "update_profile":
        # Validation
        if not request_data.get("profile_data"):
            return {"error": "Missing profile data"}

        # Update database
        db = connect_db()
        db.execute("UPDATE users SET ... WHERE id = ?", user_id)
        return {"success": True}

    elif action == "delete_user":
        # Special handling
        db = connect_db()
        db.execute("DELETE FROM users WHERE id = ?", user_id)
        return {"deleted": True}

    return {"error": "Unknown action"}

How should I improve this?"""

    print("\n" + "=" * 80)
    print("DETAILED COMPARISON: Complex Function Refactoring")
    print("=" * 80)
    print("Problem: Refactor this unwieldy function")
    print()

    personas = [
        ("🏃 Fast Coder", CodingPersonas.fast_coder),
        ("🧪 Test-Focused Coder", CodingPersonas.test_focused_coder),
        ("👨‍💼 Senior Engineer", CodingPersonas.senior_engineer),
        ("🏗️ Architect", CodingPersonas.architect),
    ]

    for name, factory in personas:
        print(f"{name}:")
        print("-" * 60)

        try:
            persona = factory()
            response = persona.ask(problem)

            # Show key points from response
            lines = response.split("\n")
            key_lines = []
            for line in lines[:10]:  # First 10 lines to see approach
                if line.strip() and not line.startswith("#"):
                    key_lines.append(line.strip())

            for _i, line in enumerate(key_lines[:5]):  # Show first 5 key points
                print(f"  • {line}")

            if len(key_lines) > 5:
                print(f"  ... (and {len(key_lines) - 5} more points)")

            print()
            persona._cleanup()

        except Exception as e:
            print(f"  Error: {e}")
            print()


if __name__ == "__main__":
    print("🎭 CODING PERSONAS DEMONSTRATION")
    print("=" * 80)

    # Quick test
    quick_persona_test()

    # Detailed comparison
    detailed_comparison()

    print("✅ Demo completed! Each persona has a distinct approach:")
    print("  🏃 Fast Coder: Quick implementation, iterate later")
    print("  🧪 Test-Focused: Tests first, dependency injection")
    print("  👨‍💼 Senior Engineer: Clean, maintainable code")
    print("  🏗️ Architect: System design, patterns, scalability")
