"""clean — (stretch) bulk terminate resources matching a tag.

WARNING — DESIGN-FOR-SAFETY
---------------------------
This is the most dangerous command in the CLI. Get the contract right:

  1. DEFAULT IS DRY-RUN. Without --apply the command MUST NOT touch resources.
     It only lists what WOULD be deleted.
  2. Even with --apply, you should consider printing a summary count first
     ("about to terminate N EC2 + M volumes — proceed?"), though for this
     starter a hard `--apply` flag is enough.
  3. Never use this with a tag you don't fully own. Reflection prompt in
     README covers the blast-radius scenario.

WHAT YOU MUST BUILD
-------------------
1. `_find_targets(tag_key, tag_val)` — return a dict like:
     {"ec2": [<instance ids in non-terminal state>],
      "volume": [<volume ids in 'available' state only>]}
   Skip terminated/shutting-down instances (already gone).
   Skip in-use volumes (can't delete while attached — would error anyway).

2. `run(args)` — call _find_targets, print the plan, then either:
     - bail with "(dry-run — pass --apply to ...)"  (default)
     - or actually terminate (when --apply)

HELPERS YOU CAN USE
-------------------
From commands._common:
  parse_kv(s) -> (k, v)

AWS APIS YOU'LL NEED
--------------------
- ec2.describe_instances() + describe_volumes() — same as list_cmd
- ec2.terminate_instances(InstanceIds=[...])
- ec2.delete_volume(VolumeId=...)  (per volume, no bulk API)

VERIFY
------
    pytest tests/test_clean.py -v
"""
import boto3

from commands._common import parse_kv


def _find_targets(tag_key, tag_val):
    """Return {"ec2": [...], "volume": [...]} matching tag in non-terminal state."""
    ec2 = boto3.client("ec2")
    targets = {"ec2": [], "volume": []}

    # Instances
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate():
        for r in page.get("Reservations", []):
            for inst in r.get("Instances", []):
                state = inst.get("State", {}).get("Name")
                if state in ("terminated", "shutting-down"):
                    continue
                tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                if tags.get(tag_key) == tag_val:
                    targets["ec2"].append(inst["InstanceId"])

    # Volumes — only include 'available' (not in-use)
    vpaginator = ec2.get_paginator("describe_volumes")
    for page in vpaginator.paginate():
        for vol in page.get("Volumes", []):
            state = vol.get("State")
            if state != "available":
                continue
            tags = {t["Key"]: t["Value"] for t in vol.get("Tags", [])}
            if tags.get(tag_key) == tag_val:
                targets["volume"].append(vol["VolumeId"])

    return targets


def run(args):
    """Entry point.

    Args set by argparse:
        args.tag    — "key=value" string (REQUIRED)
        args.apply  — bool, must be True to actually delete (default False = dry-run)
    """
    # parse tag
    tag_key, tag_val = parse_kv(args.tag)
    targets = _find_targets(tag_key, tag_val)

    total = sum(len(v) for v in targets.values())
    if total == 0:
        print("Nothing to clean")
        return

    # Print plan
    print(f"Plan to clean tag {tag_key}={tag_val} — {total} resource(s):")
    if targets["ec2"]:
        print(f"  EC2: {targets['ec2']}")
    if targets["volume"]:
        print(f"  Volumes: {targets['volume']}")

    if not args.apply:
        print("(dry-run — pass --apply to actually terminate)")
        return

    # apply: terminate instances
    ec2 = boto3.client("ec2")
    if targets["ec2"]:
        try:
            ec2.terminate_instances(InstanceIds=targets["ec2"])
            print("Terminated EC2 instances")
        except Exception as e:
            print(f"AWS error: {e}")

    # delete volumes
    for vid in targets["volume"]:
        try:
            ec2.delete_volume(VolumeId=vid)
            print(f"Deleted volume {vid}")
        except Exception as e:
            print(f"AWS error: {e}")
