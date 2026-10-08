#compdef btc-toolkit
# zsh completion for btc-toolkit — static, no dependencies.
# Install: copy into a directory on your $fpath as _btc-toolkit, e.g.
#   cp btc-toolkit.zsh ~/.zsh/completions/_btc-toolkit
_btc_toolkit() {
    local -a commands common
    commands=(
        'opreturn:Decode OP_RETURN messages from a transaction'
        'tx:Full transaction details'
        'address:Aggregated address overview'
        'balance:Confirmed + unconfirmed balance'
        'fees:Recommended fee rates + mempool backlog'
        'block:Block metadata by height, hash, or latest'
        'utxo:Unspent outputs of an address'
    )
    if (( CURRENT == 2 )); then
        _describe 'command' commands
        return
    fi
    # Each command gets exactly the flags it accepts.
    common=(
        '--json[Output as JSON]'
        '(-n --network)'{-n,--network}'[Bitcoin network]:network:(mainnet testnet signet)'
        '--api-url[Custom Mempool instance API root]:url:'
        '--timeout[Per-request timeout in seconds]:seconds:'
        '(-h --help)'{-h,--help}'[Show help]'
    )
    case $words[2] in
        fees)
            _arguments $common ;;
        opreturn)
            _arguments $common \
                '--file[Read items from file, one per line]:file:_files' \
                '--raw[Show raw hex only, one per line]' ;;
        utxo)
            _arguments $common \
                '--file[Read items from file, one per line]:file:_files' \
                '--confirmed-only[Exclude unconfirmed (mempool) UTXOs]' \
                '--limit[Max UTXOs to display (default 15)]:count:' ;;
        *)
            _arguments $common \
                '--file[Read items from file, one per line]:file:_files' ;;
    esac
}
_btc_toolkit "$@"
