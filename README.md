# servertools
Tools for administration on the student server of Osaka Univ. Medical School.

## Simple scripts
### setpublickey
Set SSH public key for arbitrary user, by root authority.
Use it in the initial settings after creating a user.

### cleanssh brothers
Now the remnant processes are automatically terminated.
You do not need to run these script.
#### cleanssh
Kill all the SSH processes of you, except the one on which this script is run.
#### cleanssh-all
Kill all the SSH processes of all users that have been idle for more than a day.

### mkuser.sh
Make a directory with a user's name and owned by the user, for all the users at the same time, at the current directory.

## clonefs
Script series to copy Btrfs/ZFS filesystems with snapshots, together with the snapshots structure, to same or different filesystems.

## loginbonus
A Slack Bot script, which list-up the members who logged in during a term (e.g. in the previous day) and post it to the specified channel automatically.

## timemachine
Time Machine backup system implemented by Python, using Btrfs (and partly compatible with ZFS) snapshot function.

## post2slack
Read message from the standard input and post it to slack.
You can split it to multiple posts, by using the `--separator` option.
