#compdef btc-toolkit
# zsh completion for btc-toolkit — static, no dependencies.
# Install: copy into a directory on your $fpath as _btc-toolkit, e.g.
#   cp btc-toolkit.zsh ~/.zsh/completions/_btc-toolkit
_btc_toolkit() {
    local -a commands
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
    _arguments \
        '--json[Output as JSON]' \
        '(-n --network)'{-n,--network}'[Bitcoin network]:network:(mainnet testnet signet)' \
        '--api-url[Custom Mempool instance API root]:url:' \
        '--timeout[Per-request timeout in seconds]:seconds:' \
        '--file[Read items from file, one per line]:file:_files' \
        '--help[Show help]'
}
_btc_toolkit "$@"
