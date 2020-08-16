# SnapShot TimeMachine

Below is an example of  `/etc/cron.d/timemachine` :
```
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
# m	h	dom	mon	dow	user	command
3	*	*	*	*	root	sstm -c /usr/local/etc/sstm/system_original.yaml / /mnt/admin/timemachine/private/system/original-snapshots && rsync --delete -aAXH --exclude '/.snapshots/' --exclude '/mnt/*/**' /mnt/admin/timemachine/private/system/original/ /mnt/admin/timemachine/private/system/backup/ && sstm -c /usr/local/etc/sstm/system_original.yaml -s backup /mnt/admin/timemachine/private/system/backup /mnt/admin/timemachine/private/system/backup-snapshots
5	*	*	*	*	root	sstm -c /usr/local/etc/sstm/home_original.yaml /home /mnt/admin/timemachine/private/home/original-snapshots && backup_home /usr/local/etc/sstm/home.excludes --delete -aAXH --max-size=100M /mnt/admin/timemachine/private/home/original/ /mnt/admin/timemachine/private/home/backup/ && sstm -c /usr/local/etc/sstm/home_backup.yaml -s backup /mnt/admin/timemachine/private/home/backup /mnt/admin/timemachine/private/home/backup-snapshots
```
