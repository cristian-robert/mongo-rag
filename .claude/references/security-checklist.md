# Pre-Ship Security Checklist

Run through this checklist before every client delivery. Every unchecked box is a risk you're choosing to ship with.

This checklist is loaded by `/validate` (Phase 2.5: Security Verification) and `/ship` (Step 1.7: Security Pre-flight).

---

## Authentication

- [ ] Passwords hashed with bcrypt or argon2 (minimum 12 rounds for bcrypt)
- [ ] Tokens stored in httpOnly cookies — not localStorage
- [ ] JWT secret is random, at least 32 characters, not from a tutorial
- [ ] Access tokens expire (15 to 60 minutes max)
- [ ] Refresh token rotation implemented
- [ ] Rate limiting on /login and /register
- [ ] Account lockout after repeated failures
- [ ] Sessions invalidated server-side on logout
- [ ] Email verification required before access granted

## API Security

- [ ] Every route verified for authentication (check all endpoints, not just obvious ones)
- [ ] Authorization checked: each user can only access their own data
- [ ] All request inputs validated with schema validation (Zod, Joi, etc.)
- [ ] API responses never include passwords, hashes, or internal fields
- [ ] Error messages don't reveal system internals or file paths
- [ ] Rate limiting on all public-facing endpoints
- [ ] CORS restricted to your domain (not wildcard `*`)
- [ ] HTTPS enforced, HTTP redirected

## Database

- [ ] No SQL string concatenation (use parameterized queries or ORM)
- [ ] Application uses a limited-permission DB user, not root
- [ ] Database not publicly accessible (behind VPC or firewall rule)
- [ ] Backups configured and restore has been tested (not just backup)
- [ ] Sensitive fields encrypted at rest

## Infrastructure

- [ ] All secrets in environment variables, not source code
- [ ] `.env` not in git history (run: `git log -- .env`)
- [ ] SSL certificate installed and valid
- [ ] Server not running as root user
- [ ] Only ports 80 and 443 publicly accessible

## Code

- [ ] No `console.log` statements in production build
- [ ] `npm audit` run, all critical vulnerabilities resolved
- [ ] No hardcoded credentials anywhere in the codebase

---

## How to Use This Checklist

### Automated Checks (run during `/validate` and `/ship`)

The following items can be verified automatically by scanning the codebase:

```bash
# Check for console.log in production code (exclude test files)
grep -r "console\.log" --include="*.ts" --include="*.js" --exclude-dir=node_modules --exclude-dir=__tests__ --exclude-dir=*.test.* . || echo "PASS: No console.log found"

# Check for hardcoded secrets patterns
grep -rn "password\s*=\s*['\"]" --include="*.ts" --include="*.js" --exclude-dir=node_modules . || echo "PASS: No hardcoded passwords"
grep -rn "secret\s*=\s*['\"]" --include="*.ts" --include="*.js" --exclude-dir=node_modules . || echo "PASS: No hardcoded secrets"
grep -rn "api[_-]key\s*=\s*['\"]" --include="*.ts" --include="*.js" --exclude-dir=node_modules . || echo "PASS: No hardcoded API keys"

# Check .env in git history
git log --all --full-history -- .env && echo "WARNING: .env found in git history" || echo "PASS: .env not in git history"

# Check for SQL string concatenation
grep -rn "query.*+.*\"\|query.*\`.*\${" --include="*.ts" --include="*.js" --exclude-dir=node_modules . || echo "PASS: No SQL concatenation detected"

# Check for wildcard CORS
grep -rn "origin:\s*['\"]\\*['\"]" --include="*.ts" --include="*.js" --exclude-dir=node_modules . || echo "PASS: No wildcard CORS"
grep -rn "Access-Control-Allow-Origin.*\\*" --include="*.ts" --include="*.js" --exclude-dir=node_modules . || echo "PASS: No wildcard CORS headers"

# Check for localStorage token storage
grep -rn "localStorage.*token\|localStorage.*jwt\|localStorage.*auth" --include="*.ts" --include="*.js" --include="*.tsx" --include="*.jsx" --exclude-dir=node_modules . || echo "PASS: No tokens in localStorage"

# Run npm audit
npm audit --audit-level=critical 2>/dev/null || echo "SKIP: npm audit not available"
```

### Manual Review Items

The following require human judgment during code review:

- **Authentication flow:** Verify password hashing algorithm and rounds, token expiration settings, refresh token rotation logic
- **Authorization:** Confirm each endpoint checks that the requesting user owns the resource
- **Rate limiting:** Verify rate limit configuration exists on auth and public endpoints
- **Infrastructure:** Confirm deployment config doesn't run as root, DB is not publicly exposed, only 80/443 are open
- **Backup testing:** Confirm restore procedure has been tested, not just backup creation

### Checklist Verdict

After running the checklist:
- **All items checked:** Security verification PASSED
- **Non-critical items unchecked:** Security verification PASSED WITH WARNINGS — list unchecked items
- **Critical items unchecked (auth, SQL injection, hardcoded secrets):** Security verification FAILED — must fix before shipping
