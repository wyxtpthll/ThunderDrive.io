#append .bashrc file
#[[ -s "/pathtofile/thunderdrive.autocomplete.bash" ]] && source /pathtofile/thunderdrive.autocomplete.bash


autocomplete_thunderdrive()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    #echo $prev

    opts="-h --help --search --useproxy --list --prompt --interactive --uploadfile --uploadmode --downloadmode --targetdir --disableprogressbar"
    COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
}

complete -f -F autocomplete_thunderdrive thunderdrive.py

