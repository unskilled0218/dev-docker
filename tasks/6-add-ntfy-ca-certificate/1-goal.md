- [command](#command)
- [goal](#goal)

## command

Copy `ntfy.lanCA.crt` like `git.lanCA.crt` when building `base.Dockerfile`.

## goal

Include `ntfy.lanCA.crt` in the base image build context and copy it into `/usr/local/share/ca-certificates/` alongside `git.lanCA.crt`, so the existing certificate update trusts both certificates.
