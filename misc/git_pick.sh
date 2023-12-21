#!/usr/bin/env bash

Help="Given a Git rev-id and list of strings $0 searches \
branch starting from rev-id for commits whose 'git log' lines contain at \
least one string given. \
Selected commit hashes are printed to stdout, other messages to stderr.\n\
\n\
Example:\n\n\
git cherry-pick \$($0 branch_name \\\\\n\
a_SHA1 \\\\\n\
'author name' \\\\\n\
'commit: message prefix' \\\\\n\
2>>/dev/null)\n\
"

Usage="\
usage: $0 [-h] [--help] [-[-]arg-to-git-log [..]] rev-id string [string [..]]"


ArgsToGitLog=( )

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
		echo "argument to git log: $1" 1>&2
		ArgsToGitLog+=( "$1" )
		;;
	esac
	shift
done
IFS=$IFSBack


if [[ 0 == $# ]]
then
	echo "no rev-id" 1>&2
	echo "$Usage" 1>&2
	exit 1
fi

LogRevId=$1
shift


IFSBack=$IFS
IFS=$'\n'
LogLines=( $(git log "${ArgsToGitLog[@]}" "$LogRevId") )
IFS=$IFSBack

if [[ 0 == ${#LogLines[@]} ]]
then
	echo "no log for rev-id $LogRevId" 1>&2
	echo "$Usage" 1>&2
	exit 1
fi


SearchedStrings=( "$@" )

if [[ 0 == ${#SearchedStrings[@]} ]]
then
	echo "no strings for commit selection from $LogRevId" 1>&2
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
		# Assume that `commit` is always first line of log record.
		AlreadySelected=0
	elif [[ 1 == $AlreadySelected ]]
	then
		# Skip rest lines of the log record. It's already selected.
		continue
	fi

	for SS in ${SearchedStrings[*]}
	do
		if [[ "$Line" == *"$SS"* ]]
		then
			echo "$SS -> $RevId $Line" 1>&2

			# reverse order
			ToCherryPick=($RevId "${ToCherryPick[@]}")

			AlreadySelected=1
			break
		fi
	done
done
IFS=$IFSBack

for RevId in ${ToCherryPick[*]}
do
	echo "$RevId"
done
