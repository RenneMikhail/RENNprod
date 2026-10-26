# Local authentication

Implemented for the loopback Python backend, not for GitHub Pages. Public docs/ contains demonstration records only.

Create local accounts interactively (password is never a command argument):

```sh
cd src/team-routing
python3 auth.py create-user --username owner --role owner
python3 auth.py create-user --username manager --role manager
python3 auth.py create-user --username specialist --role employee --specialist-id PROFILE_ID
```

Open `/login` on the loopback server. No account or password is created automatically. Existing processes must be restarted to load this code.

Passwords use salted scrypt; opaque sessions are stored hashed, expire after eight hours and can be revoked. Cookies are HttpOnly and SameSite=Strict. Mutation endpoints retain the local CSRF header and same-origin checks. Employee reads return only their own records. Manager approval/add permissions are separate and absent by default; owner can delegate via `/api/accounts/permissions`. Editing qualification-related profile fields resets qualification verification.

The server remains bound to 127.0.0.1. Production remote hosting still needs HTTPS, operational hardening and independent review. This implementation is not a claim of production security. GitHub Pages cannot run this backend or authenticate access to private records.

The running original runtime and its database have not been migrated by these changes. Source interfaces still need final integration with these endpoints.
