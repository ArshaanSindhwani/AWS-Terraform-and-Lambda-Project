import os
from urllib.parse import unquote_plus

import boto3


s3 = boto3.client("s3")


def strip_exif(jpeg):
    """Remove EXIF APP1 segments while leaving JPEG image data unchanged."""
    if len(jpeg) < 4 or jpeg[:2] != b"\xff\xd8":
        raise ValueError("Object is not a valid JPEG stream")

    output = bytearray(jpeg[:2])
    position = 2

    while position < len(jpeg):
        if jpeg[position] != 0xFF:
            raise ValueError("Malformed JPEG marker stream")

        marker_start = position
        while position < len(jpeg) and jpeg[position] == 0xFF:
            position += 1
        if position >= len(jpeg):
            raise ValueError("Truncated JPEG marker")

        marker = jpeg[position]
        position += 1

        # Markers without a length field.
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            output.extend(jpeg[marker_start:position])
            continue

        if marker == 0xD9:
            output.extend(jpeg[marker_start:position])
            break

        if position + 2 > len(jpeg):
            raise ValueError("Truncated JPEG segment length")
        segment_length = int.from_bytes(jpeg[position : position + 2], "big")
        if segment_length < 2:
            raise ValueError("Invalid JPEG segment length")
        segment_end = position + segment_length
        if segment_end > len(jpeg):
            raise ValueError("Truncated JPEG segment")

        is_exif = (
            marker == 0xE1
            and jpeg[position + 2 : position + 8] == b"Exif\x00\x00"
        )
        if not is_exif:
            output.extend(jpeg[marker_start:segment_end])
        position = segment_end

        if marker == 0xDA:
            # Scan data can contain marker-like bytes. Ignore escaped FF00
            # bytes and restart markers, then resume parsing at the next real
            # marker so EXIF segments between progressive scans are removed too.
            scan_position = position
            while True:
                scan_position = jpeg.find(b"\xff", scan_position)
                if scan_position == -1:
                    output.extend(jpeg[position:])
                    position = len(jpeg)
                    break

                next_marker = scan_position + 1
                while next_marker < len(jpeg) and jpeg[next_marker] == 0xFF:
                    next_marker += 1
                if next_marker >= len(jpeg):
                    raise ValueError("Truncated JPEG scan")

                marker_code = jpeg[next_marker]
                if marker_code == 0x00 or 0xD0 <= marker_code <= 0xD7:
                    scan_position = next_marker + 1
                    continue

                output.extend(jpeg[position:scan_position])
                position = scan_position
                break

    return bytes(output)


def lambda_handler(event, context):
    destination_bucket = os.environ["DEST_BUCKET"]

    for record in event.get("Records", []):
        source_bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        if not key.lower().endswith(".jpg"):
            continue

        response = s3.get_object(Bucket=source_bucket, Key=key)
        cleaned_jpeg = strip_exif(response["Body"].read())
        s3.put_object(
            Bucket=destination_bucket,
            Key=key,
            Body=cleaned_jpeg,
            ContentType="image/jpeg",
        )

    return {"statusCode": 200}
