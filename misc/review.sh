#!/bin/sh
#\
exec tclsh "$0" "$@"

set manual \
"
To add a review follow those steps.
1.  Create and checkout a review* branch starting at commit to be reviewed.
    E.g.: review_0, review_1, ...
2.  Add review (comments) by modifying a file(s).
3.  'git add' and 'commit' changes to the review branch.
4.  Go to step 2 to add more review for the commit being reviewed.
5.  Go to step 1 to add review to other commits in the reviewed branch.
6.  Checkout the branch being reviewed or another branch starting on last
    commit of the review branch (actually after/on last review fork).
7.  Run '\$argv0'.
    It will list review* branches and build a commit sequence from review*
    branches.
    Then the tool choose first non-cherry-picked commit in the sequence and
    cherry-pick it onto current branch.
    Order of commits in from one review branch is preserved.
    Order of review branch appending matches order of fork commits in the
    reviewed branch.
    List of cherry-picked commits is maintained in .review.state file.
8.  Resolve possible conflicts as during regular cherry-pick.
9.  Go to step 7 until all review commits are cherry-picked.
10. Run '\$argv0 -clean' to remove review* branches.
    The tool does not remove a branch that have a non-cherry-picked commit.
11. Go to step 1 to review other branch.
"

set verb 0
set mode "normal"

proc main {} {
    global verb
    global mode

    global argspec
    global argv
    global argc
    set i 0
    while {$i < $argc} {
        set arg [lindex $argv $i]
        incr i

        if {[string index $arg 0] == "-"} {
            set is_arg 1
        } else {
            set is_arg 0
        }
        if $is_arg {
            switch -regexp $arg [preprocess_argspec $argspec]
        } else {
            unsupported_cli_arg $arg
        }
    }

    if $verb {puts "mode $mode"}

    # get review branches
    global branches
    set branches [list]
    set branches_io [open {|git branch --list} r]

    fforeach branch $branches_io {
        set branch [string trim $branch " *"]
        if {![startswith $branch review]} {continue}
        lappend branches $branch
    }
    close $branches_io

    global head_sha
    set head_sha [sha HEAD]
    if $verb {puts "HEAD SHA1 $head_sha"}

    "do_$mode"
}

set argspec {
    "v|verbose" "Verbose mode" {
        set verb 1
    }
    "clean"  "Delete all review* branches" {
        set mode "clean"
    }
    "h|help" "Pring help message" {
        global argv0
        global argspec

        puts "Supported arguments (as regular expression)"

        set i 0
        while {$i < [llength $argspec]} {
            set pattern [lindex $argspec $i]
            incr i
            if {"$pattern" != "default"} {
                set message [lindex $argspec $i]
                incr i
                puts "  -($pattern)"
                puts "      $message"
            }
            # skip handler
            incr i
        }
        exit 0
    }
    "m|man|manual" "Print a manual" {
        global manual
        global argv0
        if 1 "puts \"$manual\""
    }
    "default" {
        unsupported_cli_arg [lindex $argv [expr $i - 1]]
    }
}

proc preprocess_argspec {argspec} {
    set res [list]

    set i 0
    while {$i < [llength $argspec]} {
        set pattern [lindex $argspec $i]
        incr i
        if {"$pattern" != "default"} {
            set docstring [lindex $argspec $i]
            incr i
            set pattern "^-+($pattern)$"
        }
        set handler [lindex $argspec $i]
        incr i
        lappend res $pattern $handler
    }

    return $res
}

proc unsupported_cli_arg {arg} {
    puts "Unsupported argument $arg"
    global argv0
    puts [exec "$argv0" "-h"]
    exit 1
}

proc do_normal {} {
    global verb
    global branches

    set cherry_pick [list]

    foreach branch $branches {
        set ins_pos [llength $cherry_pick]
        if $verb {puts "ins_pos $ins_pos"}

        foreach commit [commits_to_cherry_pick $branch] {
            # rev-list returns commits from newest to elder, reverse it
            set cherry_pick [linsert $cherry_pick $ins_pos $commit]
        }
    }

    if $verb {puts "cherry pick order: $cherry_pick"}

    set cherry_picked [read_cherry_picked]

    if $verb {puts "already cherry picked [llength $cherry_picked]"}

    foreach commit $cherry_pick {
        if {[lsearch $cherry_picked $commit] >= 0} {continue}
        puts "cherry-picking $commit"
        mark_cherry_picked $commit

        set git_io [open |[list "git" "cherry-pick" $commit 2>&1] r]
        while {1} {
            if {[gets $git_io line] < 0} {break}
            puts $line
        }
        close $git_io
        # TODO: detect errors (e.g. merge conflicts)
        # TODO: break only after errors
        break
    }
}

proc do_clean {} {
    global verb
    global branches

    set cherry_picked [read_cherry_picked]
    set skipped_branches [list]

    foreach branch $branches {
        set not_cherry_picked ""
        foreach commit [commits_to_cherry_pick $branch] {
            if {[lsearch $cherry_picked $commit] < 0} {
                set not_cherry_picked $commit
                break
            }
        }

        if {$not_cherry_picked != "" } {
            puts "Branc $branch has at least one not cherry-picked commit"
            puts "   $not_cherry_picked"
            lappend skipped_branches $branch
            continue
        }

        if $verb {puts "deleting $branch"}

        run_command "git" "branch" "-D" "$branch"
    }

    if {[llength $skipped_branches] == 0} {
        # all review branches have been deleted (review ended)
        if {[file exists ".review.state"]} {
            if $verb {puts "removing .review.state"}
            file delete ".review.state"
        }
    }
}

proc run_command {args} {
    set args [linsert $args end 2>@1]
    set io [open |$args r]
    fforeach line $io {puts $line}
    catch {close $io}
}


# returns commits of review
proc commits_to_cherry_pick {branch} {
    global verb
    global head_sha

    set ret [list]

    set branch_sha [sha $branch]
    if $verb {puts "$branch $branch_sha"}
    set start_sha [git merge-base $branch $head_sha]
    if $verb {puts "Merge base: $start_sha"}

    # get commits of review
    set log_io [open "|git rev-list $start_sha..$branch_sha" r]
    fforeach line $log_io {
        if $verb {puts $line}
        lappend ret $line
    }
    close $log_io
    return $ret
}

proc mark_cherry_picked {commit} {
    set io [open ".review.state" a+]
    puts $io $commit
    close $io
}

proc read_cherry_picked {} {
    if {![file exists ".review.state"]} {
        return [list]
    }

    set io [open ".review.state" r]
    set ret [list]
    fforeach line $io {lappend ret $line}
    return $ret
}

proc sha {rev} {
    return [git rev-parse $rev]
}

proc git {args} {
    return [first_line "git $args"]
}

proc first_line {cmd} {
    set io [open "|$cmd" r]
    if {[gets $io line] < 1} {
        set line ""
    }
    close $io
    return $line
}

proc fforeach {var io cb} {
    while {1} {
        if {[gets $io line] < 0} break
        uplevel 1 "set $var \"$line\"; $cb"
    }
}

proc startswith {line prefix} {
    return [expr [string first "$prefix" "$line"] == 0]
}

main
