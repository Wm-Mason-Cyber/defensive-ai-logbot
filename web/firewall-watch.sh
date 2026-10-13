#!/bin/sh
# firewall-watch.sh — the "enforcement point" half of the firewall.
#
# The official nginx image runs every executable script in /docker-entrypoint.d/
# before starting nginx. This one starts a small background loop that checks
# the blocklist every second and, when it changes, validates the config
# (nginx -t) and hot-reloads nginx without dropping connections.
#
# The SOC broker only writes a file. This loop is what applies it, the same
# way a real policy engine pushes rules to firewalls it does not run on.

BLOCKLIST_DIR=/etc/nginx/blocklist
OUT=/proc/1/fd/1   # container stdout → visible in `docker compose logs web`

fingerprint() {
    cat "$BLOCKLIST_DIR"/*.conf 2>/dev/null | md5sum | cut -d' ' -f1
}

count_rules() {
    cat "$BLOCKLIST_DIR"/*.conf 2>/dev/null | grep -c '^[[:space:]]*deny'
}

(
    last="$(fingerprint)"
    echo "[firewall] watching $BLOCKLIST_DIR ($(count_rules) active rules)" > "$OUT"
    while true; do
        sleep 1
        now="$(fingerprint)"
        [ "$now" = "$last" ] && continue
        if nginx -t -q 2> /tmp/nginx-test.err; then
            nginx -s reload
            echo "[firewall] blocklist changed -> reloaded nginx ($(count_rules) active rules)" > "$OUT"
        else
            echo "[firewall] REJECTED invalid blocklist, keeping previous rules:" > "$OUT"
            cat /tmp/nginx-test.err > "$OUT"
        fi
        last="$now"
    done
) &
