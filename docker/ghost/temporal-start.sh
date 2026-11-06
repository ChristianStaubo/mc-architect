#!/bin/sh
# Temporal's auto-setup reads the database password from POSTGRES_PWD; ours lives in a file.
POSTGRES_PWD="$(cat /run/ghost/db-password)"
export POSTGRES_PWD
exec /etc/temporal/entrypoint.sh autosetup
