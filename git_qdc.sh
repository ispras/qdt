#!/bin/bash

# This script is designed to aid user to change device template automatic
# creation parameters after some custom logic were implemented. It tries to
# create device template with new parameters and then apply custom changes.
#
# The script relies on Git. Both initial device creation and consequent
# re-creations should be made involving the script. Each one is assigned a
# commit created by the script. It actually tracks last automatically created
# commit using a tag. On template update (it actually generates new device
# template) script trunks from the tag, creating a commit with new version of
# template. Then it rebases custom changes on new template. The resolution of
# possible conflicts with correct rebase complation is up to user.
#
# The implementation requires a specific branch should be created per device.
# It is not theoretically necessary but it forces user to follow well
# workflow.
#
# This is prof-of-concept implementation mostly because of the QDC is not
# implemented external configuration yet. The script should evolve with QDC.

# Extra parameters
QemuSrc="/home/real/work/qemu/src"
QDCSuffix="qemu_device_creator.py"

# Constants
BranchRegEx="^[a-zA-Z_][a-zA-Z_0-9]*$"

PrevPWD=`pwd`

if [ "$1" == "" ] ; then
    echo "A branch must be specified (1-st argument)."
    exit 1
fi

if ! [ -f "$2" ] ; then
    echo "A project file must be specified (2-nd argument)."
    exit 1
fi

if [ "$3" == "" ] ; then
    echo "No commit message was provided (3-rd argument). Default one will be \
used."
    Msg="QDC auto commit"
else
    Msg="$3"
fi

if ! [[ "$1" =~ $BranchRegEx ]] ; then
    echo "Branch name '$1' does not matches '$BranchRegEx'."
    exit 1
fi

function _git() {
    git --git-dir="$QemuSrc/.git" --work-tree="$QemuSrc" "$@"
}

GitStatus=`_git status -s`
if ! [ "${GitStatus}" == "" ] ; then
    echo "The repository have changes. Cannot proceed."
    _git status
    exit 1
fi

Tag="${1}_QDC"
StartTag="${Tag}_start"
LastTag="${Tag}_last"
DirName=`dirname "$0"`
QDC="$DirName/$QDCSuffix"

CurrentBranch=`_git rev-parse --abbrev-ref HEAD`
#echo "$CurrentBranch"

BranchExists=`_git show-ref "$1"`
#echo "$BranchExists"

if [ "$BranchExists" == "" ] ; then
    echo "First generation."

    if _git tag "$StartTag" ; then
        echo "Start tag has been set ($StartTag)."
    else
        echo "Cannot set start tag ($StartTag)."
        exit 1
    fi

    if _git branch "$1" ; then
        if _git checkout "$1" ; then
            if python "$QDC" "$2" ; then
                if _git add -A ; then
                    if _git commit -m "$Msg" ; then
                        if _git tag "$LastTag" ; then
                            echo "Success"
                            exit 0
                        else
                            echo "Cannot create auxilliary tag '$LastTag'. \
Automatic update will fail. Manual recovery is needed!"
                        fi
                    else
                        echo "Cannot commit generated code."
                    fi
                    # Undo adding changes to index.
                    _git reset
                else
                    echo "Cannot add generated code to index."
                fi
            else
                echo "QDC have failed."
            fi
            # Remove changes made by QDC script (they could be made even in
            # case of error).
            _git checkout .
            git clean -f 
            _git checkout "$CurrentBranch"
        else
            echo "Failed checkout just created branch '$1'."
        fi
        _git branch -d "$1"
    else
        echo "Failed create branch with name '$1'."
    fi
else
    echo "Update."

    NewBase="${1}_QDC_tmp"
    PreviousBase="${1}_QDC_tmp2"

    if _git checkout "$StartTag" ; then
        if _git branch "$NewBase" ; then
            if _git checkout "$NewBase" ; then
                if python "$QDC" "$2" ; then
                    if _git add -A ; then
                        if _git commit -m "$Msg" ; then
if _git checkout -b "$PreviousBase" "$LastTag" ; then
    if _git cherry-pick --strategy-option theirs "$NewBase" ; then
        if _git rebase --onto "$PreviousBase" "$LastTag" "$CurrentBranch" ; then
            echo "Automatic update have done."
        else
            # Is there a conflict ?
            echo "Conflict? If yes then you should \
resolve it then execute 'git rebase --continue' (see Git's message above). \
Else there are some unexpected case. Manual solution is required in both cases."
        fi
        # Move tag
        if _git tag -d "$LastTag" ; then
            if ! _git tag "$LastTag" "$PreviousBase" ; then
                echo "Cannot create new auxilliary tag '$LastTag'. Next update \
will fail. Manual recovery is needed!"
            fi
        else
            echo "Cannot remove previous auxilliary tag '$LastTag'. Next \
update will be confused. Manual recovery is needed!"
        fi
        _git checkout "$CurrentBranch"
        _git branch -D "$NewBase"
        _git branch -D "$PreviousBase"
        exit 0
    else
        echo "Cannot cherry pick new version of base onto old base."
        _git merge --abort
    fi
    _git checkout "$NewBase"
    _git branch -D "$PreviousBase"
fi
                        else
                            echo "Cannot commit newly generated code."
                        fi
                        _git reset
                    else
                        echo "Cannot stage changes."
                    fi
                else
                    echo "QDC have failed."
                fi
                _git checkout .
                git clean -f 
                _git checkout "$CurrentBranch"
            else
                echo "Cannot switch to temporary branch '$NewBase'."
            fi
            _git branch -d "$NewBase"
        else
            echo "Cannot create branch for new base'$NewBase'."
        fi
        _git checkout "$CurrentBranch"
    else
        echo "Cannot checkout start tag '$StartTag'."
    fi
fi

exit 1


