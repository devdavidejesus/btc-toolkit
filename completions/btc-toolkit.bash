# bash completion for btc-toolkit — static, no dependencies.
# Install: source this file from ~/.bashrc, e.g.
#   echo 'source /path/to/btc-toolkit.bash' >> ~/.bashrc
_btc_toolkit() {
    local cur prev commands
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
    esac
    COMPREPLY=( $(compgen -W "--json --network --api-url --timeout --file --help" -- "${cur}") )
}
complete -F _btc_toolkit btc-toolkit
