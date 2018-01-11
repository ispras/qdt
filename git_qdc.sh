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
DirName=`dirname "$0"`
QDC="$DirName/$QDCSuffix"

CurrentBranch=`_git rev-parse --abbrev-ref HEAD`
#echo "$CurrentBranch"

BranchExists=`_git show-ref "$1"`
#echo "$BranchExists"

if [ "$BranchExists" == "" ] ; then
    echo "Creating new device."

    if _git branch "$1" ; then
        if _git checkout "$1" ; then
            if python "$QDC" "$2" ; then
                if _git add -A ; then
                    if _git commit -m "QDC auto commit" ; then
                        if _git tag "$Tag" ; then
                            echo "Success"
                            exit 0
                        else
                            echo "Cannot create auxilliary tag '$Tag'. \
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
    echo "Updating device."

    TmpBranch="${1}_QDC_tmp"

    if _git checkout "$Tag" ; then
        if _git branch "$TmpBranch" ; then
            if _git checkout "$TmpBranch" ; then
                if python "$QDC" "$2" ; then
                    if _git add -A ; then
                        if _git commit -m "QDC auto commit" ; then
                            # Move tag
                            if _git tag -d "$Tag" ; then
                                if _git tag "$Tag" ; then
                                    if _git rebase "$TmpBranch" \
                                                        "$CurrentBranch" ; then
                                        echo "Automatic update have done."
                                    else
                                        # Is there a conflict ?
                                        echo "Conflict? If yes then you should \
resolve it then execute 'git rebase --continue' (see Git's message above). \
Else there are some unexpected case. Manual solution is required in both cases."
                                    fi
                                    _git branch -d "$TmpBranch"
                                    exit 0
                                else
                                    echo "Cannot create new auxilliary tag \
'$Tag'. Automatic update will fail. Manual recovery is needed!"
                                fi
                            else
                                echo "Cannot remove previous auxilliary tag \
'$Tag'."
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
                echo "Cannot switch to temporary branch '$TmpBranch'."
            fi
            _git branch -d "$TmpBranch"
        else
            echo "Cannot create temporary branch '$TmpBranch'."
        fi
        _git checkout "$CurrentBranch"
    else
        echo "Cannot checkout auxilliary tag '$Tag'."
    fi
fi

exit 1


