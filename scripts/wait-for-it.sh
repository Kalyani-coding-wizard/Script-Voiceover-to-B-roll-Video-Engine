#!/usr/bin/env bash
# wait-for-it.sh — wait for a TCP host:port to become available.
# Usage: wait-for-it.sh host:port [-s] [-t timeout] [-- command [args]]
#   -h HOST | --host=HOST        Host or IP to test
#   -p PORT | --port=PORT        TCP port to test
#   -s | --strict                Only execute subcommand if the test succeeds
#   -q | --quiet                 Suppress output
#   -t TIMEOUT | --timeout=TIMEOUT  Timeout in seconds (default 15, 0 = no timeout)
#   -- COMMAND ARGS              Command to execute after the test finishes
#
# Source: https://github.com/vishnubob/wait-for-it (MIT License)
# Vendored here so the container does not need internet at runtime.

WAITFORIT_cmdname=${0##*/}

echoerr() { if [[ $WAITFORIT_QUIET -ne 1 ]]; then echo "$@" 1>&2; fi }

usage() {
    cat << USAGE >&2
Usage:
    $WAITFORIT_cmdname host:port [-s] [-t timeout] [-- command args]
    -h HOST | --host=HOST          Host or IP under test
    -p PORT | --port=PORT          TCP port under test
    -s | --strict                  Only execute subcommand if test succeeds
    -q | --quiet                   Do not output any status messages
    -t TIMEOUT | --timeout=TIMEOUT Timeout in seconds, 0 for no timeout
    -- COMMAND ARGS                Execute command with args after the test finishes
USAGE
    exit 1
}

wait_for() {
    if [[ $WAITFORIT_TIMEOUT -gt 0 ]]; then
        echoerr "$WAITFORIT_cmdname: waiting $WAITFORIT_TIMEOUT seconds for $WAITFORIT_HOST:$WAITFORIT_PORT"
    else
        echoerr "$WAITFORIT_cmdname: waiting for $WAITFORIT_HOST:$WAITFORIT_PORT without a timeout"
    fi
    WAITFORIT_start_ts=$(date +%s)
    while :; do
        if [[ $WAITFORIT_ISBUSY -eq 1 ]]; then
            nc -z $WAITFORIT_HOST $WAITFORIT_PORT
            WAITFORIT_result=$?
        else
            (echo -n > /dev/tcp/$WAITFORIT_HOST/$WAITFORIT_PORT) >/dev/null 2>&1
            WAITFORIT_result=$?
        fi
        if [[ $WAITFORIT_result -eq 0 ]]; then
            WAITFORIT_end_ts=$(date +%s)
            echoerr "$WAITFORIT_cmdname: $WAITFORIT_HOST:$WAITFORIT_PORT is available after $((WAITFORIT_end_ts - WAITFORIT_start_ts)) seconds"
            break
        fi
        sleep 1
        WAITFORIT_timeout=$((WAITFORIT_TIMEOUT - ($(date +%s) - WAITFORIT_start_ts)))
        if [[ $WAITFORIT_TIMEOUT -gt 0 && $WAITFORIT_timeout -le 0 ]]; then
            echoerr "$WAITFORIT_cmdname: timeout occurred after waiting $WAITFORIT_TIMEOUT seconds for $WAITFORIT_HOST:$WAITFORIT_PORT"
            return 1
        fi
    done
    return 0
}

wait_for_wrapper() {
    # In order to support SIGINT during timeout: http://unix.stackexchange.com/a/57692
    if [[ $WAITFORIT_QUIET -eq 1 ]]; then
        timeout $WAITFORIT_BUSYTIMEFLAG $WAITFORIT_TIMEOUT bash $0 --quiet --child --host=$WAITFORIT_HOST --port=$WAITFORIT_PORT --timeout=$WAITFORIT_TIMEOUT &
    else
        timeout $WAITFORIT_BUSYTIMEFLAG $WAITFORIT_TIMEOUT bash $0 --child --host=$WAITFORIT_HOST --port=$WAITFORIT_PORT --timeout=$WAITFORIT_TIMEOUT &
    fi
    WAITFORIT_PID=$!
    trap "kill -INT -$WAITFORIT_PID" INT
    wait $WAITFORIT_PID
    WAITFORIT_RESULT=$?
    if [[ $WAITFORIT_RESULT -ne 0 ]]; then
        echoerr "$WAITFORIT_cmdname: timeout occurred after waiting $WAITFORIT_TIMEOUT seconds for $WAITFORIT_HOST:$WAITFORIT_PORT"
    fi
    return $WAITFORIT_RESULT
}

# Parse positional args
WAITFORIT_QUIET=0
WAITFORIT_STRICT=0
WAITFORIT_CHILD=0
WAITFORIT_TIMEOUT=15
WAITFORIT_ISBUSY=0
WAITFORIT_BUSYTIMEFLAG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        *:* )
        WAITFORIT_hostport=(${1//:/ })
        WAITFORIT_HOST=${WAITFORIT_hostport[0]}
        WAITFORIT_PORT=${WAITFORIT_hostport[1]}
        shift 1
        ;;
        --child) WAITFORIT_CHILD=1; shift 1 ;;
        -q | --quiet) WAITFORIT_QUIET=1; shift 1 ;;
        -s | --strict) WAITFORIT_STRICT=1; shift 1 ;;
        -h) WAITFORIT_HOST="$2"; shift 2 ;;
        --host=*) WAITFORIT_HOST="${1#*=}"; shift 1 ;;
        -p) WAITFORIT_PORT="$2"; shift 2 ;;
        --port=*) WAITFORIT_PORT="${1#*=}"; shift 1 ;;
        -t) WAITFORIT_TIMEOUT="$2"; shift 2 ;;
        --timeout=*) WAITFORIT_TIMEOUT="${1#*=}"; shift 1 ;;
        --) shift; WAITFORIT_CLI=("$@"); break ;;
        --help) usage ;;
        *) echoerr "Unknown argument: $1"; usage ;;
    esac
done

if [[ "$WAITFORIT_HOST" == "" || "$WAITFORIT_PORT" == "" ]]; then
    echoerr "Error: you need to provide a host and port to test."
    usage
fi

WAITFORIT_TIMEOUT=${WAITFORIT_TIMEOUT:-15}
WAITFORIT_STRICT=${WAITFORIT_STRICT:-0}
WAITFORIT_CHILD=${WAITFORIT_CHILD:-0}
WAITFORIT_QUIET=${WAITFORIT_QUIET:-0}

# Check to see if timeout is from busybox
if [[ $WAITFORIT_TIMEOUT -gt 0 ]]; then
    # Busy-box has a different command option requirement
    timeout 1 true
    if [[ $? -eq 0 ]]; then
        WAITFORIT_ISBUSY=0
        WAITFORIT_BUSYTIMEFLAG=""
    else
        WAITFORIT_ISBUSY=1
        WAITFORIT_BUSYTIMEFLAG="-t"
    fi
fi

if [[ $WAITFORIT_CHILD -gt 0 ]]; then
    wait_for
    WAITFORIT_RESULT=$?
    exit $WAITFORIT_RESULT
else
    if [[ $WAITFORIT_TIMEOUT -gt 0 ]]; then
        wait_for_wrapper
        WAITFORIT_RESULT=$?
    else
        wait_for
        WAITFORIT_RESULT=$?
    fi
fi

if [[ ${#WAITFORIT_CLI[@]} -gt 0 ]]; then
    if [[ $WAITFORIT_RESULT -ne 0 && $WAITFORIT_STRICT -eq 1 ]]; then
        echoerr "$WAITFORIT_cmdname: strict mode, refusing to execute subprocess"
        exit $WAITFORIT_RESULT
    fi
    exec "${WAITFORIT_CLI[@]}"
else
    exit $WAITFORIT_RESULT
fi
