#!/bin/bash
export PS1='$ '
type_cmd() { printf '$ '; for ((i=0;i<${#1};i++)); do printf '%s' "${1:$i:1}"; sleep 0.03; done; sleep 0.5; printf '\n'; eval "$1"; }
clear
type_cmd "btc-toolkit opreturn c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19"
sleep 3.5
clear
type_cmd "btc-toolkit opreturn d7e8837c51cc625c2c6365d371d376b035209fa01434d4933971d6428d6d6d52"
sleep 3.5
