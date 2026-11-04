- [command](#command)
- [goal](#goal)

## command

copy penpot.lanCA.crt like git.lanCA.crt or ntfy.lanCA.crt

## goal

Include `penpot.lanCA.crt` in the base image build context and copy it into `/usr/local/share/ca-certificates/` alongside the Git and ntfy certificates, using the same certificate input handling so the existing trust update trusts all three.
