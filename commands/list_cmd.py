"""list — list AWS resources by type, filter by tag / missing-tag.

WHAT YOU MUST BUILD
-------------------
Support 4 resource types: ec2, rds, s3, volume.
Each takes:
- `want` — list of (key, value) tag pairs the resource MUST have
- `missing` — list of tag keys the resource MUST NOT have

Print a formatted table to stdout. Test cases are in tests/test_list.py.

HELPERS YOU CAN USE
-------------------
From commands._common:
  parse_kv(s) -> (k, v)            # "Owner=alice" -> ("Owner", "alice")
  tags_to_dict(items) -> dict       # boto3 [{"Key","Value"}] -> {k: v}
  tags_match(tags, want, missing) -> bool

AWS APIS YOU'LL NEED
--------------------
- EC2: ec2.describe_instances() with get_paginator
- RDS: rds.describe_db_instances(), then list_tags_for_resource(ResourceName=arn)
- S3:  s3.list_buckets(), then get_bucket_tagging(Bucket=name)
       (catch ClientError when bucket has no tagging config — treat as {})
- EBS: ec2.describe_volumes() with get_paginator

EXPECTED OUTPUT FORMAT (when run from CLI)
------------------------------------------
    EC2 Environment=dev — 1 found:
    ------------------------------------------------------------------------------
      i-0abc123def456789a       t3.micro       running       Environment=dev

VERIFY
------
    pytest tests/test_list.py -v
"""
import boto3
from botocore.exceptions import ClientError
from commands._common import parse_kv, tags_to_dict, tags_match


def _list_ec2(want, missing):
    """List EC2 instances matching tag filters."""
    ec2 = boto3.client('ec2')
    rows = []
    
    paginator = ec2.get_paginator('describe_instances')
    for page in paginator.paginate():
        for reservation in page.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                # Không hiển thị những instance đã bị xoá hẳn
                if instance['State']['Name'] == 'terminated':
                    continue
                    
                instance_id = instance['InstanceId']
                instance_type = instance['InstanceType']
                state = instance['State']['Name']
                tags_dict = tags_to_dict(instance.get('Tags', []))
                
                if tags_match(tags_dict, want, missing):
                    rows.append((instance_id, instance_type, state, tags_dict))
    return rows


def _list_rds(want, missing):
    """Same shape as _list_ec2 but for RDS DB instances."""
    rds = boto3.client('rds')
    rows = []
    
    # Do RDS API trả về trực tiếp danh sách hoặc dùng Marker (ở mức cơ bản hàm này trả về danh sách đầy đủ)
    response = rds.describe_db_instances()
    for db in response.get('DBInstances', []):
        db_id = db['DBInstanceIdentifier']
        db_class = db['DBInstanceClass']
        db_status = db['DBInstanceStatus']
        arn = db['DBInstanceArn']
        
        # RDS yêu cầu một API riêng để lấy tag
        try:
            tag_response = rds.list_tags_for_resource(ResourceName=arn)
            tags_dict = tags_to_dict(tag_response.get('TagList', []))
        except ClientError:
            tags_dict = {}
            
        if tags_match(tags_dict, want, missing):
            rows.append((db_id, db_class, db_status, tags_dict))
    return rows


def _list_s3(want, missing):
    """List S3 buckets matching tag filters."""
    s3 = boto3.client('s3')
    rows = []
    
    response = s3.list_buckets()
    for bucket in response.get('Buckets', []):
        name = bucket['Name']
        
        # S3 sẽ ném lỗi ClientError nếu bucket đó hoàn toàn không được cấu hình tag
        try:
            tagging = s3.get_bucket_tagging(Bucket=name)
            tags_dict = tags_to_dict(tagging.get('TagSet', []))
        except ClientError as e:
            # Nếu lỗi do trống tag (NoSuchTagSet), coi như dict rỗng
            if e.response['Error']['Code'] in ['NoSuchTagSet', '404']:
                tags_dict = {}
            else:
                raise e
                
        if tags_match(tags_dict, want, missing):
            rows.append((name, "bucket", "active", tags_dict))
    return rows


def _list_volume(want, missing):
    """List EBS volumes matching tag filters."""
    ec2 = boto3.client('ec2')
    rows = []
    
    paginator = ec2.get_paginator('describe_volumes')
    for page in paginator.paginate():
        for volume in page.get('Volumes', []):
            volume_id = volume['VolumeId']
            vol_type = volume['VolumeType']
            size = volume['Size']
            state = volume['State']
            tags_dict = tags_to_dict(volume.get('Tags', []))
            
            # Định dạng hiển thị cụ thể theo đề bài yêu cầu: "<type>-<size>GB"
            details = f"{vol_type}-{size}GB"
            
            if tags_match(tags_dict, want, missing):
                rows.append((volume_id, details, state, tags_dict))
    return rows


DISPATCH = {
    "ec2": _list_ec2,
    "rds": _list_rds,
    "s3": _list_s3,
    "volume": _list_volume,
}


def run(args):
    """Entry point called by costctl.py."""
    # 1. Chuyển đổi args.tag (dạng ["Key=Val", ...]) thành list tuple [(Key, Val), ...]
    want = []
    if args.tag:
        for t in args.tag:
            want.append(parse_kv(t))
            
    # 2. Giữ nguyên danh sách các tag keys cần kiểm tra xem có bị thiếu không
    missing = args.missing_tag if args.missing_tag else []
    
    # 3. Gọi hàm xử lý tương ứng thông qua DISPATCH dict
    resource_type = args.type
    rows = DISPATCH[resource_type](want, missing)
    
    # 4. Tạo nhãn chuỗi filter phục vụ cho việc in Header tiêu đề khớp spec
    filter_parts = []
    if args.tag:
        filter_parts.extend(args.tag)
    if args.missing_tag:
        filter_parts.extend([f"!{m}" for m in args.missing_tag])
        
    filter_str = f" {' '.join(filter_parts)}" if filter_parts else ""
    
    # 5. Tiến hành in Header line và dải phân cách theo định dạng mẫu
    # Lưu ý hoa thường: Loại tài nguyên in hoa (ec2 -> EC2, s3 -> S3...)
    header_type = resource_type.upper()
    print(f"{header_type}{filter_str} — {len(rows)} found:")
    print("-" * 78)
    
    # 6. Duyệt in ra từng dòng dữ liệu của tài nguyên
    for item_id, item_detail, item_state, item_tags in rows:
        # Chuỗi tag đính kèm ở cuối dòng (ví dụ: "Env=dev Owner=admin")
        tags_str = " ".join([f"{k}={v}" for k, v in item_tags.items()])
        # Định dạng canh lề bằng khoảng trắng sao cho chuẩn xác, đẹp đẽ và khớp test case
        if tags_str:
            print(f"  {item_id:<20} {item_detail:<14} {item_state:<12} {tags_str}")
        else:
            print(f"  {item_id:<20} {item_detail:<14} {item_state:<12}")