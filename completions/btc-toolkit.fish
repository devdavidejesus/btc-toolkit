# fish completion for btc-toolkit — static, no dependencies.
# Install: copy into a directory on your $fish_complete_path, e.g.
#   cp btc-toolkit.fish ~/.config/fish/completions/btc-toolkit.fish

# Disable file completion by default
complete -c btc-toolkit -f

# Global flags
complete -c btc-toolkit -n "__fish_use_subcommand" -s v -l version -d "Show version"
complete -c btc-toolkit -n "__fish_use_subcommand" -s h -l help -d "Show help"

# Subcommands
complete -c btc-toolkit -n "__fish_use_subcommand" -a opreturn -d "Decode OP_RETURN messages from a transaction"
complete -c btc-toolkit -n "__fish_use_subcommand" -a tx -d "Full transaction details"
complete -c btc-toolkit -n "__fish_use_subcommand" -a address -d "Aggregated address overview"
complete -c btc-toolkit -n "__fish_use_subcommand" -a balance -d "Confirmed + unconfirmed balance"
complete -c btc-toolkit -n "__fish_use_subcommand" -a fees -d "Recommended fee rates + mempool backlog"
complete -c btc-toolkit -n "__fish_use_subcommand" -a block -d "Block metadata by height, hash, or latest"
complete -c btc-toolkit -n "__fish_use_subcommand" -a utxo -d "Unspent outputs of an address"
complete -c btc-toolkit -n "__fish_use_subcommand" -a validate -d "Check an address offline (checksum, network, type)"
complete -c btc-toolkit -n "__fish_use_subcommand" -a inscription -d "Ordinals inscription envelopes in a transaction"
complete -c btc-toolkit -n "__fish_use_subcommand" -a decode -d "Decode a raw transaction offline"
complete -c btc-toolkit -n "__fish_use_subcommand" -a verify -d "Check a transaction is in a block (Merkle proof + work)"

# Common flags (accepted by all subcommands)
set -l commands opreturn tx address balance fees block utxo validate inscription decode verify
complete -c btc-toolkit -n "__fish_seen_subcommand_from $commands" -l json -d "Output as JSON"
complete -c btc-toolkit -n "__fish_seen_subcommand_from $commands" -s n -l network -x -a "mainnet testnet signet" -d "Bitcoin network"
complete -c btc-toolkit -n "__fish_seen_subcommand_from $commands" -l api-url -r -d "Custom Mempool instance API root"
complete -c btc-toolkit -n "__fish_seen_subcommand_from $commands" -l timeout -r -d "Per-request timeout in seconds"
complete -c btc-toolkit -n "__fish_seen_subcommand_from $commands" -s h -l help -d "Show help"

# Batch file input (all subcommands except fees and decode)
set -l file_commands opreturn tx address balance block utxo validate inscription verify
complete -c btc-toolkit -n "__fish_seen_subcommand_from $file_commands" -l file -r -F -d "Read items from file, one per line"

# Command-specific flags
complete -c btc-toolkit -n "__fish_seen_subcommand_from opreturn" -l raw -d "Show raw hex only, one per line"
complete -c btc-toolkit -n "__fish_seen_subcommand_from utxo" -l confirmed-only -d "Exclude unconfirmed (mempool) UTXOs"
complete -c btc-toolkit -n "__fish_seen_subcommand_from utxo" -l limit -r -d "Max UTXOs to display (default 15)"
complete -c btc-toolkit -n "__fish_seen_subcommand_from tx" -l inputs -d "List each input"
complete -c btc-toolkit -n "__fish_seen_subcommand_from tx" -l outputs -d "List each output and whether it is spent"
complete -c btc-toolkit -n "__fish_seen_subcommand_from decode" -l txid -r -d "Fetch the raw transaction of this txid"
