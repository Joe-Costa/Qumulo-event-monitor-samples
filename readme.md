# Qumulo File System Event Monitor

**This repo is provided as code and idead examples only**

This project uses the Qumulo Change Notify API to monitor for changes to a watched portion of the file system and triggers the launching of modules in response to specific conditions.

The workflow would consist of:

- A script which initiates a Change Notify API subscription and listens for events

- `watched_items.yml`  A file containing a list of watched directories, files or file extensions and the actions to take when matched

- `cn_monitor.conf` A file containing the target QAumulo cluster and credential info

- A Docker or Kubernetes deployment to run all of the above.

## RBAC privileges required

This script requires a valid session token for a user with the following RBAC privilege:

`['PRIVILEGE_FILE_READ_ACCESS']`

![RBAC](./screenshot/rbac.png)

## Helpful Qumulo Care Articles:

[How to get an Access Token](https://care.qumulo.com/hc/en-us/articles/360004600994-Authenticating-with-Qumulo-s-REST-API#acquiring-a-bearer-token-by-using-the-web-ui-0-3) 

[Qumulo Role Based Access Control](https://care.qumulo.com/hc/en-us/articles/360036591633-Role-Based-Access-Control-RBAC-with-Qumulo-Core#managing-roles-by-using-the-web-ui-0-7)


## Hypothetical sample workflow:

1. An event watcher script monitors all recursive changes to a cluster's root directory
2. Changes are pushed into a queue (Redis, most likely)
3. A event subscriber polls the Redis queue and filters for matches in a watched items config file
4. Matches then trigger the appropriate Action Module.

Notes:

The Event Filter should ideally have AND/OR condition matching logic and should also allow the application of changes to the `watched_items.conf` file without stopping `cn_monitor.py` or losing events.

## Example of an event:

`{'type': 'child_file_added', 'spine': ['2', '10003', '5007655', '1459590167'], 'path': 'home/joe/fff2', 'stream_name': None}`

## Sample Possible Action Modules:

- Quarantine specific file types (.jpg, .zip, .mp4, etc)
- Trigger `all_stop.py` if a set of watched files are modified
- Rename files in a watched directory
- Change permissions on files in a watched directory
- Send an email or message if a file or directory has been changed or created (Integrate with Qumulo Email Alerts?)

## Note if writing back to cluster as an action:

We need to be mindful to include logic to prevent any endless loops of Actions being triggered by the result of the Actions themselves showing up in the Monitor output!
