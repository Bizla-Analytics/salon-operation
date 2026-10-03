# Staff visibility and password recovery

Development branch: `dev`. These changes do not deploy unless explicitly committed
and pushed through the configured release process.

## General manager

- Open **All staff** in the sidebar or business overview.
- View employees and managers across all branches, even without an acting duty.
- Search by name, username, staff code or home branch. Lists show 24 people per page.
- Cards show home branch, today's working branch, leave/inactive status and open services.
- Reset active employee passwords across branches, including employees on leave.

## Branch manager

- Open **All staff → Reset password**.
- Password recovery follows today's effective roster: a covering employee can be
  reset by their current branch manager, not by their home branch manager.
- Employees working elsewhere or on leave have no reset button for the branch
  manager. Ask the general manager to help instead.
- A manager on leave cannot reset staff passwords or use branch operations.

## Reset flow

1. Open the employee's reset page.
2. Enter **your own current password** to authorize recovery.
3. Enter and confirm a strong new employee password, then submit.
4. Share the password privately. Ask the employee to use **Profile → Change
   password** to choose their own password; this last step is not automatically forced.

The employee's old password and sessions stop working. The manager stays signed
in. Roster records, assignments, visit history and task snapshots are unchanged.
Only employee accounts can be reset here; manager, general-manager, administrator,
inactive and Django-privileged accounts are excluded.

Each successful reset writes an existing Django admin audit entry identifying
the actor and employee, without storing either plaintext password. Server-side
scope checks run again when the form is submitted; CSRF protection and Django
password validators apply. No new database model or migration is required.

Managers and every other role can still change their **own** password through
**Profile → Change password** using their current password.

For the session behavior, see the
[Django authentication documentation](https://docs.djangoproject.com/en/5.2/topics/auth/default/#session-invalidation-on-password-change).
