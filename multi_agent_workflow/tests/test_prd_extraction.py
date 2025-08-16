#!/usr/bin/env python3
"""Test script to verify PRD feature extraction functionality."""

import tempfile
from pathlib import Path


def create_test_prd():
    """Create a test PRD file with multiple features."""
    prd_content = """# Product Requirements Document

## Overview
This PRD outlines the features for our new application.

## Features

### Feature 1: User Authentication
#### Description
Implement a secure user authentication system with the following capabilities:
- User registration with email verification
- Login with email/password
- Password reset functionality
- Session management

#### Requirements
- Use JWT tokens for authentication
- Implement rate limiting on login attempts
- Store passwords using bcrypt hashing
- Support OAuth2 integration (Google, GitHub)

#### Acceptance Criteria
- Users can register with email and password
- Email verification is required before login
- Password reset sends secure token via email
- Sessions expire after 24 hours of inactivity

### Feature 2: Dashboard
#### Description
Create a comprehensive dashboard for users to view their data.

#### Requirements
- Real-time data updates
- Customizable widgets
- Export functionality

### Feature 3: API Integration
#### Description
Build RESTful APIs for third-party integrations.

#### Requirements
- OpenAPI specification
- Rate limiting
- API key authentication
"""
    return prd_content


def main():
    """Test the PRD extraction functionality."""
    print("Testing PRD Feature Extraction")
    print("=" * 50)
    
    # Create a temporary PRD file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        prd_content = create_test_prd()
        f.write(prd_content)
        prd_file = f.name
    
    print(f"Created test PRD at: {prd_file}")
    print("\nTest scenarios:")
    print("1. Extract 'User Authentication' feature:")
    print(f"   python step1_analysis.py --prd-file {prd_file} --feature 'User Authentication' --codebase-analysis-only")
    print("\n2. Extract 'Dashboard' feature:")
    print(f"   python step1_analysis.py --prd-file {prd_file} --feature 'Dashboard' --codebase-analysis-only")
    print("\n3. Try to extract non-existent feature:")
    print(f"   python step1_analysis.py --prd-file {prd_file} --feature 'Nonexistent Feature' --codebase-analysis-only")
    
    print("\nNote: Added --codebase-analysis-only to skip full analysis for testing")
    print(f"\nPRD file saved at: {prd_file}")
    print("You can manually run the commands above to test the extraction.")


if __name__ == "__main__":
    main()