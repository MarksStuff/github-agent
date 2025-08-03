# User Authentication v2

Implement a modern user authentication system for our web application with support for multiple authentication methods and enhanced security features.

## Requirements:
- Support email/password authentication with secure password hashing
- Implement OAuth2 integration for Google and GitHub login
- Add two-factor authentication (2FA) using TOTP
- Create JWT-based session management with refresh tokens
- Implement password reset functionality with secure token generation
- Add account lockout after failed login attempts
- Support "Remember Me" functionality with persistent sessions
- Create user profile management endpoints
- Log all authentication events for security auditing

## Acceptance Criteria:
- Users can register with email and password
- Passwords are hashed using bcrypt with appropriate cost factor
- OAuth login works seamlessly with Google and GitHub
- 2FA can be enabled/disabled by users with QR code generation
- JWT tokens expire after 15 minutes, refresh tokens after 30 days
- Password reset emails are sent with secure, time-limited tokens
- Account locks after 5 failed attempts, unlocks after 30 minutes
- All endpoints have proper input validation and error handling
- Authentication events are logged with user IP and user agent
- API documentation is complete with example requests/responses

## Constraints:
- Must maintain compatibility with existing user database schema
- Cannot break existing API clients (deprecation period required)
- Must comply with GDPR requirements for user data
- Performance impact should be minimal (<50ms added latency)
- Must use existing email service for notifications