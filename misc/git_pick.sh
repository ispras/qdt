#!/usr/bin/env bash

Help="Given a Git rev-id and list of regular expressions $0 searches \
branch starting from rev-id for commits whose 'git log' lines matches at \
least one regular expression given. \
Selected commit hashes are printed to stdout, other messages to stderr.\n\
\n\
Example:\n\n\
git cherry-pick \$($0 branch_name \\\\\n\
'feature regular expression' \\\\\n\
'author name' \\\\\n\
'commit message prefix' \\\\\n\
2>>/dev/null)\n\
"

Usage="usage: $0 [-h] [--help] rev-id regex [regex [...]]"


IFSBack=$IFS
IFS=$'\n'
while [[ "$1" =~ ^-.+$ ]]
do
	case "$1" in
	"-h" )
		echo "$Usage" 1>&2
		echo -e "\n$Help" 1>&2
		exit 0
		;;
	"--help" )
		echo "$Usage" 1>&2
		echo -e "\n$Help" 1>&2
		exit 0
		;;
	* )
		echo "unknown argument $1" 1>&2
		echo "$Usage" 1>&2
		exit 1
		;;
	esac
	shift
done
IFS=$IFSBack


LogRevId=$1
shift


IFSBack=$IFS
IFS=$'\n'
LogLines=( $(git log -q "$LogRevId") )
IFS=$IFSBack

if [[ 0 == ${#LogLines[@]} ]]
then
	echo "no log for rev-id $LogRevId" 1>&2
	echo "$Usage" 1>&2
	exit 1
fi


MessagesRe=( "$@" )

if [[ 0 == ${#MessagesRe[@]} ]]
then
	echo "no regular expressions for commit selection from $LogRevId" 1>&2
	echo "$Usage" 1>&2
	exit 1
fi

ToCherryPick=( )

IFSBack=$IFS
IFS=$'\n'
for Line in ${LogLines[*]}
do
	if [[ "$Line" =~ ^commit\ ([a-f0-9]+)$ ]]
	then
		RevId="${BASH_REMATCH[1]}"
	fi
	for Re in ${MessagesRe[*]}
	do
		if [[ "$Line" =~ "$Re" ]]
		then
			echo "$Re -> $RevId $Line" 1>&2

			AlreadySelected=0
			for SelectedRevId in ${ToCherryPick[*]}
			do
				if [ $SelectedRevId == $RevId ]
				then
					AlreadySelected=1
					break
				fi
			done

			if [[ 1 == $AlreadySelected ]]
			then
				echo "$RevId: multiple match, take once" 1>&2
			else
				# reverse order
				ToCherryPick=($RevId "${ToCherryPick[@]}")
			fi
		fi
	done
done
IFS=$IFSBack

for RevId in ${ToCherryPick[*]}
do
	echo "$RevId"
done
