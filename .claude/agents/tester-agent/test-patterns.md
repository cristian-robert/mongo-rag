# MongoRAG Test Patterns

## Base URL
http://localhost:3000

## Key Pages & What to Expect

### Marketing Homepage (/)
- Hero section with product description
- Pricing section or CTA
- Navigation header with login/signup links

### Pricing (/pricing)
- Plan cards (Free, Pro, Enterprise or similar)
- Feature comparison
- CTA buttons linking to signup

### Login (/login)
- Email + password fields
- "Forgot password" link
- "Register" link
- OAuth buttons (if implemented)

### Register (/register)
- Email, password, confirm password fields
- Terms acceptance checkbox
- Submit button

### Dashboard (/dashboard)
- Overview stats (documents count, queries, usage)
- Quick actions (upload document, view API keys)
- Recent activity

### Documents (/documents)
- Document list with title, status, date
- Upload button/dropzone
- Delete/edit actions per document

### API Keys (/api-keys)
- List of API keys (prefix shown, full key hidden)
- Create new key button
- Delete/revoke actions

### Settings (/settings)
- Profile settings
- Notification preferences
- Account management

### Billing (/billing)
- Current plan display
- Usage meters
- Upgrade/downgrade options
- Payment method management

## Common UI Elements
- Header: logo, navigation, user menu (when authenticated)
- Sidebar: dashboard navigation (when in dashboard)
- Toast notifications for success/error
- Loading states: skeleton placeholders

## Auth-Required Pages
These redirect to /login if not authenticated:
/dashboard, /documents, /api-keys, /settings, /billing

## Form Patterns
- Validation errors appear inline below fields (red text)
- Submit buttons show loading spinner when processing
- Success → toast + redirect
- Error → toast with error message
