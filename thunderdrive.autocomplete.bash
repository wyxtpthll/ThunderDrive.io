#append .bashrc file
#[[ -s "/pathtofile/thunderdrive.autocomplete.bash" ]] && source /pathtofile/thunderdrive.autocomplete.bash


thunderdrive_autocomplete()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    #echo $prev

    #case "${prev}" in
    #    -t | --tmpdir | -a | --tarfile | -p | --passwdfile)
    #        COMPREPLY=( $(compgen -f ${cur}) )
    #        return 0
    #        ;;
    #    *)
    #        ;;
    #esac

    opts="-h --help -s --search --useproxy --list --prompt --interactive --upload --uploadfile -u"
    COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    #wwcrypt --autocomplete
}

#complete -o filenames -o bashdefault -f -F wwcrypt_autocomplete wwcrypt
complete -f -F thunderdrive_autocomplete thunderdrive

