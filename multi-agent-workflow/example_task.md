# Task: User Authentication System

## Overview
Create a user authentication system with the following capabilities:
- User registration with email and password
- User login with JWT token generation
- Password hashing and validation
- Token refresh mechanism
- User profile management

## Design Requirements

### Data Model
- User entity with fields:
  - id (UUID)
  - email (unique)
  - hashed_password
  - created_at
  - updated_at
  - is_active

### API Endpoints
1. POST /auth/register
   - Input: email, password
   - Output: user_id, message
   
2. POST /auth/login
   - Input: email, password
   - Output: access_token, refresh_token
   
3. POST /auth/refresh
   - Input: refresh_token
   - Output: new_access_token
   
4. GET /auth/profile
   - Headers: Authorization Bearer token
   - Output: user profile data

5. PUT /auth/profile
   - Headers: Authorization Bearer token
   - Input: profile updates
   - Output: updated profile

## Acceptance Criteria

1. **Security**
   - Passwords must be hashed using bcrypt or similar
   - JWT tokens should have appropriate expiration times
   - Refresh tokens should be stored securely
   - Input validation on all endpoints

2. **Error Handling**
   - Proper HTTP status codes
   - Clear error messages
   - No sensitive information in error responses

3. **Testing**
   - Unit tests for all core functions
   - Integration tests for API endpoints
   - Test coverage > 80%

4. **Code Quality**
   - Type hints throughout
   - Proper logging
   - Configuration through environment variables
   - Clear separation of concerns

## Technical Constraints
- Python 3.10+
- Use existing project structure
- Follow project's coding standards
- Compatible with existing database setup