# bash completion for btc-toolkit — static, no dependencies.
# Install: source this file from ~/.bashrc, e.g.
#   echo 'source /path/to/btc-toolkit.bash' >> ~/.bashrc
_btc_toolkit() {
    local cur prev commands flags
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="opreturn tx address balance fees block utxo"

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${commands} --help --version" -- "${cur}") )
        return 0
    fi
    case "${prev}" in
        -n|--network)
            COMPREPLY=( $(compgen -W "mainnet testnet signet" -- "${cur}") )
            return 0 ;;
        --file)
            COMPREPLY=( $(compgen -f -- "${cur}") )
            return 0 ;;
        --api-url|--timeout|--limit)
            return 0 ;;
    esac
    # Each command gets exactly the flags it accepts.
    flags="--json --network --api-url --timeout --help"
    case "${COMP_WORDS[1]}" in
        fees)     ;;
        opreturn) flags="${flags} --file --raw" ;;
        utxo)     flags="${flags} --file --confirmed-only --limit" ;;
        *)        flags="${flags} --file" ;;
    esac
    COMPREPLY=( $(compgen -W "${flags}" -- "${cur}") )
}
complete -F _btc_toolkit btc-toolkit
