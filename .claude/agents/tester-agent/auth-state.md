# Auth State

Test credentials for the tester-agent. Fill in when setting up the project.

## Test User

- **Email:** test@example.com
- **Password:** testpassword123

## Login Flow

1. Navigate to `/login`
2. Fill email field
3. Fill password field
4. Click submit button
5. Wait for redirect to `/dashboard`

## Session Management

- Auth state is stored in browser cookies/localStorage
- If session expires, re-run the login flow above
- For persistent state, save browser state after login
