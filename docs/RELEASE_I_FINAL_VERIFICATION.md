# Release I — v4.0.0 Final Verification Checklist

## Automated gate

- [ ] Python 3.12 CI PASS
- [ ] Python 3.13 CI PASS
- [ ] full characterization suite PASS
- [ ] Release C–H regression gates PASS
- [ ] Release I baseline drift gate PASS
- [ ] no schema change
- [ ] no AI-routing change
- [ ] no discovery authorization expansion

## Production boot gate

- [ ] Railway deployment SUCCESS
- [ ] persistent volume mounted at `/data`
- [ ] DB `/data/akane_v26.db` initialized
- [ ] schema version unchanged
- [ ] persistent views loaded
- [ ] four production extensions loaded
- [ ] 19 top-level slash commands synced
- [ ] Discord Gateway connected
- [ ] bot READY

## Human Verification

- [ ] READ_ONLY discovery/direct execution
- [ ] parameterized capability flow
- [ ] WRITE_CONFIRM cancel = zero mutation
- [ ] benign WRITE_CONFIRM confirmed execution
- [ ] AI-generation parameter flow
- [ ] native Scheduled Event creation/visibility
- [ ] ticket persistent UI survives restart
- [ ] ADMIN requester-only confirmation and cancel
- [ ] MODERATION confirmation shown; destructive action not required
- [ ] ordinary conversation still falls back to AI chat
- [ ] no unexpected duplicate response / interaction timeout

## Acceptance

- [ ] Human Verification PASS
- [ ] Human Acceptance CONFIRMED
- [ ] v4.0.0 Production Baseline frozen
