#!/bin/bash
# Shared operational helpers for the quantitative reconciliation tooling.

QUANT_LOG_TIMESTAMP="false"

quant_log() {
    local level="$1"
    shift
    if [[ "${QUANT_LOG_TIMESTAMP}" == "true" ]]; then
        printf '[%s] %s: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$level" "$*"
    else
        printf '%s: %s\n' "$level" "$*"
    fi
}

quant_info() {
    quant_log INFO "$@"
}

quant_warn() {
    quant_log WARN "$@"
}

quant_error() {
    quant_log ERROR "$@" >&2
}

quant_die() {
    local message="$1"
    shift
    quant_error "$message${*:+: $*}"
    exit 1
}

quant_require_tools() {
    local tool
    for tool in "$@"; do
        command -v "$tool" >/dev/null 2>&1 || quant_die "required tool is unavailable" "$tool"
    done
}

quant_is_decimal() {
    local value="$1"
    [[ "$value" =~ ^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$ ]]
}

quant_is_identifier() {
    local value="$1"
    [[ "$value" =~ ^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$ ]]
}

quant_sql_quote() {
    local value="$1"
    printf "'%s'" "${value//\'/\'\'}"
}

quant_read_header_field() {
    local spool="$1"
    local header_bytes="$2"
    local field="$3"
    dd if="$spool" bs=1 count="$header_bytes" status=none 2>/dev/null |
        sed -n "s/^${field}:[[:space:]]*//p" | head -n 1
}

quant_validate_mode() {
    local path="$1"
    local expected="$2"
    local actual
    actual="$(stat -c '%a' "$path")"
    [[ "$actual" == "$expected" ]] || quant_die "unexpected directory mode" "$path=$actual expected=$expected"
}
